import os
from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.tools import clone_isolated_workspace, execute_xcodebuild, read_workspace_file, write_workspace_file, post_github_comment
from agent.llm_factory import get_llm
from pydantic import BaseModel, Field
from typing import List

class FileModification(BaseModel):
    filepath: str = Field(description="Absolute path to the file.")
    purpose: str = Field(description="Exact architectural reason this file requires creation/modification.")

class FeatureBlueprint(BaseModel):
    """The master architectural plan for the requested feature."""
    feature_name: str = Field(description="Name of the feature being built.")
    files_to_create: List[FileModification]
    files_to_modify: List[FileModification]
    files_to_test: List[FileModification] = Field(
        description="Mandatory array of XCTest suites to enforce TDD. Must contain at least 1 test file."
    )
    architecture_components: List[str] = Field(
        description="List of design tokens/architecture patterns utilized (e.g. Construkt.bgPrimary, MVVM)."
    )


def initialize_workspace_node(state: AgentState):
    task_id = state.get("task_id", "default_task")
    repo_url = state.get("repo_url", "")
    
    # Using the tool to clone
    result = clone_isolated_workspace(task_id, repo_url)
    actual_path = os.path.join(os.path.dirname(__file__), "..", ".workspaces", task_id)
    branch_name = f"ios-agent-issue-{task_id}"
    
    return {
        "workspace_path": actual_path,
        "current_branch": branch_name,
        "history": [f"Initialized workspace at {actual_path}"]
    }

def planner_node(state: AgentState):
    llm = get_llm(role="planning").with_structured_output(FeatureBlueprint)
    instructions = state.get("instructions", "")
    
    prompt = f"You are the Lios Architect Agent. Design a strict architecture plan for this issue:\n{instructions}\nEnsure you mandate TDD by defining the XCTest suites."
    blueprint: FeatureBlueprint = llm.invoke(prompt)
    
    return {
        "blueprint": blueprint.dict(),
        "history": [f"Planning Step Complete: Generated FeatureBlueprint for {blueprint.feature_name}"]
    }

def blueprint_presentation_node(state: AgentState):
    blueprint_dict = state.get("blueprint", {})
    repo_full_name = state.get("repo_full_name")
    task_id = state.get("task_id")
    installation_id = state.get("installation_id")
    
    # Format the blueprint as a Github Markdown table
    md = f"### 🏗️ Lios-Agent Architectural Blueprint: {blueprint_dict.get('feature_name', 'Feature')}\n\n"
    
    md += "**Files to Create:**\n"
    for f in blueprint_dict.get("files_to_create", []):
        md += f"- `{f['filepath']}`: {f['purpose']}\n"
        
    md += "\n**Files to Modify:**\n"
    for f in blueprint_dict.get("files_to_modify", []):
        md += f"- `{f['filepath']}`: {f['purpose']}\n"
        
    md += "\n**Files to Test (TDD Enforcement):**\n"
    for f in blueprint_dict.get("files_to_test", []):
        md += f"- `{f['filepath']}`: {f['purpose']}\n"
        
    md += f"\n**Architecture Components:** `{', '.join(blueprint_dict.get('architecture_components', []))}`\n\n"
    md += "---\n*Please reply with **Approve** to execute this graph.*"
    
    if repo_full_name and installation_id:
        post_github_comment(repo_full_name, task_id, installation_id, md)
        
    return {"history": ["Blueprint posted to GitHub. Suspended thread awaiting approval."]}

def coder_node(state: AgentState):
    llm = get_llm(role="coding")
    workspace_path = state.get("workspace_path")
    
    # Bind the filesystem tools to the LLM
    tools = [read_workspace_file, write_workspace_file]
    llm_with_tools = llm.bind_tools(tools)
    
    prompt = f"You are tasked with fixing this issue: {state.get('instructions')}\nUse your tools to read files and write the fixes in workspace: {workspace_path}"
    
    # Inject compiler errors if this is a feedback loop
    if state.get("compiler_errors"):
        prompt += f"\n\nWARNING. PREVIOUS BUILD FAILED WITH ERRORS:\n{state.get('compiler_errors')[-1]}\nPlease use your tools to fix these compile errors."
        
    result = llm_with_tools.invoke(prompt)
    return {"history": ["Coding Step Complete (Code modifications requested via AI tool binding)."]}

def validator_node(state: AgentState):
    workspace_path = state.get("workspace_path")
    task_id = state.get("task_id")
    build_output = execute_xcodebuild(workspace_path)
    
    if "Build SUCCESS" in build_output:
        # Send Approval Request to Slack
        slack_channel = os.environ.get("SLACK_CHANNEL_ID")
        bot_token = os.environ.get("SLACK_BOT_TOKEN")
        if slack_channel and bot_token:
            from slack_sdk import WebClient
            client = WebClient(token=bot_token)
            try:
                client.chat_postMessage(
                    channel=slack_channel,
                    text=f"Validation Passed for Task {task_id}",
                    blocks=[
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"✅ *AI Build Passed for Task #{task_id}*\n The Xcode build in the isolated workspace succeeded. Would you like me to push this code?"}
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "Approve & Push"},
                                    "style": "primary",
                                    "action_id": "approve_pr",
                                    "value": str(task_id)
                                }
                            ]
                        }
                    ]
                )
            except Exception as e:
                print(f"Failed to post Slack approval: {e}")
                
        return {"history": ["Xcode Build Validation PASSED! Awaiting human approval in Slack."]}
    else:
        errors = state.get("compiler_errors", [])
        errors.append(build_output)
        retries = state.get("retries_count", 0) + 1
        return {
            "compiler_errors": errors,  
            "retries_count": retries,
            "history": [f"Xcode Build Failed. Retry count: {retries}"]
        }

def should_retry(state: AgentState) -> str:
    """Conditional Edge logic: decides if we go back to CoderNode or give up."""
    # Break out to approval phase if successful
    if "PASSED" in state.get("history", [])[-1]:
        return "checkout"
        
    # Safeguard against infinite loops and clean corrupted states
    if state.get("retries_count", 0) >= 3:
        workspace_path = state.get("workspace_path")
        if workspace_path:
            import subprocess
            print("🚨 Max retries hit! Executing RTK State Rollback...")
            subprocess.run(["rtk", "git", "clean", "-fd"], cwd=workspace_path, check=False)
            subprocess.run(["rtk", "git", "checkout", "--", "."], cwd=workspace_path, check=False)
        return "checkout"
        
    return "coder" # Feedback loop: go back to coding to fix the compiler error

def issue_vetting_node(state: AgentState):
    llm = get_llm(role="planning")
    instructions = state.get("instructions", "")
    
    prompt = f"""You are the initial filter for an iOS Agentic Coder. 
Review the following GitHub Issue:
{instructions}

If the issue is clear enough to attempt finding/fixing code (it mentions a component, feature, or clear request), simply reply 'ACTIONABLE'.
If the issue is vague, dummy testing text, or lacks context (e.g. "dummy message", "fix the app"), write a short polite comment asking the developer for clarification. Do NOT write 'ACTIONABLE'.
"""
    response = llm.invoke(prompt).content.strip()
    
    if response.upper() == "ACTIONABLE":
        return {"history": ["Issue Vetting: Actionable."]}
    else:
        # Halt and comment on GitHub
        repo_full_name = state.get("repo_full_name")
        task_id = state.get("task_id")
        installation_id = state.get("installation_id")
        
        from agent.tools import post_github_comment
        if repo_full_name and installation_id:
            post_github_comment(repo_full_name, task_id, installation_id, response)
            
        return {"history": ["Issue Vetting: Failed. Commented on GitHub and halted."]}

def should_proceed_from_vetting(state: AgentState) -> str:
    if "halted." in state.get("history", [""])[-1]:
        return "end"
    return "initialize"

def build_graph():
    """Compiles the LangGraph State Machine."""
    graph = StateGraph(AgentState)
    
    graph.add_node("vetting", issue_vetting_node)
    graph.add_node("initialize", initialize_workspace_node)
    graph.add_node("planner", planner_node)
    graph.add_node("blueprint_presentation", blueprint_presentation_node)
    graph.add_node("coder", coder_node)
    graph.add_node("validator", validator_node)
    graph.add_node("push", lambda state: {"history": ["Code pushed and PR opened."]}) 
    
    # Wiring the flow
    graph.set_entry_point("vetting")
    
    graph.add_conditional_edges("vetting", should_proceed_from_vetting, {
        "initialize": "initialize",
        "end": END
    })
    
    graph.add_edge("initialize", "planner")
    graph.add_edge("planner", "blueprint_presentation")
    graph.add_edge("blueprint_presentation", "coder")
    graph.add_edge("coder", "validator")
    
    # Conditional logic out of the validator
    graph.add_conditional_edges("validator", should_retry, {
        "coder": "coder",     # Loop back
        "checkout": "push"    # Proceed to Approval -> Push
    })
    
    graph.add_edge("push", END)
    
    # Attach memory so the graph can be paused waiting for Slack human approval
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    app = graph.compile(checkpointer=checkpointer, interrupt_before=["coder", "push"])
    
    return app
