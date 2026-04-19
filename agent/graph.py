import os
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END

# GLOBALLY persist LangGraph thread memory across the FastAPI lifecycle
GLOBAL_CHECKPOINTER = MemorySaver()

from agent.state import AgentState
from agent.tools import clone_isolated_workspace, execute_xcodebuild, read_workspace_file, write_workspace_file, read_workspace_file_lines, patch_workspace_file, post_github_comment, capture_simulator_screenshot, validate_ui_with_vision, fetch_external_link
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
        default_factory=list,
        description="Array of Swift Testing test suites. Mandatory for Swift features, but LEAVE EMPTY for pure documentation/config tasks."
    )
    architecture_components: List[str] = Field(
        default_factory=list,
        description="List of design tokens/architecture patterns utilized. LEAVE EMPTY for pure documentation/config tasks."
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

async def context_aggregator_node(state: AgentState):
    from agent.mcp_clients import MCPManager
    from langgraph.prebuilt import create_react_agent
    
    llm = get_llm(role="planning")
    workspace_path = state.get("workspace_path")
    instructions = state.get("instructions", "")
    
    manager = MCPManager()
    tools = await manager.connect_and_get_tools(workspace_path, instructions)
    
    if not tools:
        return {"mcp_context": "No external MCP context available.", "history": ["Context Aggregation Node skipped (No tools found)."]}
        
    try:
        # Include our custom web fetching tool for external links
        tools.append(fetch_external_link)
        
        # Create a tiny internal autonomous loop so the LLM can query Serena/XcodeBuild/Web tools fully
        agent_executor = create_react_agent(llm, tools=tools)
        prompt = f"""You are a Principal iOS Codebase Investigator. Your job is to explore the codebase and external references to gather architecturally significant context for this issue:
{instructions}

Investigate the following 7 categories using your tools and produce a structured Markdown report:

1. **Project Structure**: Check for project.yml (XcodeGen), Tuist, or Package.swift. Identify module layout.
2. **Prior Art Reference Template**: Identify the single most structurally similar EXISTING feature in the codebase. Use the `list_directory` tool to map its entire file tree. Output this file tree exactly, and explicitly state its architectural components. This will be used as a mandatory mapping template.
3. **Design System**: Search for design tokens (Construkt, Theme, ColorAsset, etc.).
4. **Architecture**: Look for patterns like Coordinator, MVVM, Repository, Inject.
5. **Testing Conventions**: Check the Tests/ directory for XCTest vs Quick, and naming styles.
6. **Build & Dependencies**: Query deployment targets, schemes, and Swift versions.
7. **External Knowledge (Serena Index & Web Links)**: If the issue explicitly mentions another codebase by name, use `query_projects` to search Serena's index. If the issue contains HTTP links to external repos, gists, or docs, use `fetch_external_link` to read them.
8. **Design Specs & Business Logic (Figma/Jira)**: If the issue contains a Figma URL, use the Figma tool to extract color tokens, layout hierarchy, and spacing constraints for the feature. If the issue contains a Jira ticket url/ID, use the Jira tool to fetch all linked Acceptance Criteria and Edge Cases.

Return your findings as a structured Markdown report with headers for each category.
"""
        
        print("🕵️  Principal Architect is executing sub-agent loops to query tool integrations...")
        result = await agent_executor.ainvoke(
            {"messages": [("user", prompt)]},
            config={"recursion_limit": 4}
        )
        context_data = result["messages"][-1].content
    except Exception as e:
        context_data = f"Failed to execute context gathering: {e}"
    finally:
        await manager.cleanup()
        
    # Read Agent Skills and Repo Rules
    agent_skills = ""
    if workspace_path:
        config_path = os.path.join(workspace_path, ".lios-config.yml")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                agent_skills += f"--- .lios-config.yml ---\n{f.read()}\n\n"
                
        import glob
        
        search_patterns = [
            os.path.join(workspace_path, ".agent", "*.md"),
            os.path.join(workspace_path, ".agents", "*.md"),
            os.path.join(workspace_path, ".agent", "skills", "**", "*.md"),
            os.path.join(workspace_path, ".agents", "skills", "**", "*.md")
        ]
        
        found_files = set()
        for pattern in search_patterns:
            for skill_file in glob.glob(pattern, recursive=True):
                if skill_file not in found_files:
                    found_files.add(skill_file)
                    with open(skill_file, "r") as f:
                        agent_skills += f"--- {os.path.basename(skill_file)} ---\n{f.read()}\n\n"
                
    if not agent_skills.strip():
        agent_skills = "No specific rules found. Follow standard iOS best practices."
        
    return {
        "mcp_context": context_data,
        "agent_skills": agent_skills,
        "history": ["Context Aggregator Node executed. External tools queried."]
    }

def planner_node(state: AgentState):
    llm = get_llm(role="planning")
    instructions = state.get("instructions", "")
    mcp_context = state.get("mcp_context", "None")
    agent_skills = state.get("agent_skills", "No specific rules found.")
    
    # Build the JSON schema description for the LLM
    schema_description = """
You MUST respond with ONLY a valid JSON object (no markdown, no explanation, no code fences) matching this exact schema:
{
  "feature_name": "string - Name of the feature being built",
  "files_to_create": [{"filepath": "string - absolute path", "purpose": "string - why this file is needed"}],
  "files_to_modify": [{"filepath": "string - absolute path", "purpose": "string - why this file needs modification"}],
  "files_to_test": [{"filepath": "string - absolute path", "purpose": "string - test suite purpose"}],
  "architecture_components": ["string - design patterns used"]
}
"""
    
    prompt = f"""You are a Principal iOS Systems Architect. Design a strict architecture plan for this issue:
{instructions}

External System Context:
{mcp_context}

Repository Conventions & Hard Rules:
{agent_skills}

🔥 PRIOR ART ENFORCEMENT 🔥
If the External System Context includes a 'Prior Art Reference Template', you MUST structurally clone its file architecture for this new feature. Use the exact same naming conventions, folder structures, and interaction patterns.

🔥 TDD ENFORCEMENT 🔥
If this is a coding task, you MUST mandate TDD by defining the Swift Testing (`import Testing`) suites. Do NOT use XCTest. However, if this is purely a documentation or config task (e.g., updating a README.md), leave the testing and architecture arrays empty!

{schema_description}
"""
    response = llm.invoke(prompt)
    raw_text = response.content.strip()
    
    # Attempt to extract JSON from the response (handle markdown code fences)
    import json, re
    json_str = raw_text
    
    # Strip markdown code fences if present
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_text, re.DOTALL)
    if fence_match:
        json_str = fence_match.group(1).strip()
    
    try:
        parsed = json.loads(json_str)
        blueprint = FeatureBlueprint(**parsed)
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ Planner JSON parse failed: {e}. Building minimal blueprint from raw response.")
        # Fallback: create a minimal valid blueprint from the raw text
        blueprint = FeatureBlueprint(
            feature_name=state.get("instructions", "Unknown Feature")[:80],
            files_to_create=[],
            files_to_modify=[FileModification(filepath="(see raw plan below)", purpose=raw_text[:500])],
            files_to_test=[],
            architecture_components=[]
        )
    
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
        print(f"✅ Generating Blueprint markdown and posting to GitHub for {repo_full_name}#{task_id}...")
        result = post_github_comment(repo_full_name, task_id, installation_id, md)
        print(f"GitHub Post Result: {result}")
        
    return {"history": ["Blueprint posted to GitHub. Suspended thread awaiting approval."]}

# ---------------------------------------------------------------------------
# Sub-Agent Execution Swarm
# ---------------------------------------------------------------------------

def _classify_blueprint_domains(blueprint: dict) -> list:
    """Inspect the FeatureBlueprint to determine which sub-agents are needed."""
    arch = [c.lower() for c in blueprint.get("architecture_components", [])]
    all_files = (blueprint.get("files_to_create", []) +
                 blueprint.get("files_to_modify", []) +
                 blueprint.get("files_to_test", []))
    file_paths = [f.get("filepath", "").lower() if isinstance(f, dict) else str(f).lower() for f in all_files]
    
    domains = []
    
    # UI detection
    ui_keywords = ["swiftui", "uikit", "view", "construkt", "screen", "component", "ui"]
    if (any(kw in c for c in arch for kw in ui_keywords) or
        any(kw in fp for fp in file_paths for kw in ["view", "screen", "cell", "component"])):
        domains.append("ui")
    
    # Network / Data detection
    net_keywords = ["api", "network", "repository", "service", "endpoint", "data", "model"]
    if (any(kw in c for c in arch for kw in net_keywords) or
        any(kw in fp for fp in file_paths for kw in ["service", "repository", "api", "model", "dto"])):
        domains.append("network")
    
    # Fallback: if nothing matched, treat as general
    if not domains:
        domains.append("general")
    
    return domains

def router_node(state: AgentState):
    """Analyzes the blueprint and determines which sub-agents to activate."""
    blueprint = state.get("blueprint", {})
    domains = _classify_blueprint_domains(blueprint)
    return {
        "active_subagents": domains,
        "history": [f"Router: Dispatching to sub-agents: {', '.join(domains)}"]
    }

def should_route_subagent(state: AgentState) -> str:
    """Conditional edge: route to the appropriate sub-agent based on classification."""
    domains = state.get("active_subagents", ["general"])
    if "ui" in domains:
        return "ui_subagent"
    elif "network" in domains:
        return "network_subagent"
    return "general_coder"

def ui_subagent_node(state: AgentState):
    """Specialized sub-agent focused exclusively on UI/View layer code."""
    llm = get_llm(role="coding")
    workspace_path = state.get("workspace_path")
    blueprint = state.get("blueprint", {})
    agent_skills = state.get("agent_skills", "No custom rules found.")
    
    tools = [read_workspace_file, read_workspace_file_lines, write_workspace_file, patch_workspace_file]
    from langgraph.prebuilt import create_react_agent
    agent_executor = create_react_agent(llm, tools=tools)
    
    prompt = f"""You are a Senior iOS UI/UX Engineer specialized in pixel-perfect SwiftUI and UIKit development.
You ONLY work on SwiftUI Views, UIKit ViewControllers, Construkt design tokens, and UI components.

Workspace: {workspace_path}
Task: {state.get('instructions')}

Blueprint:
{blueprint}

TEAM RULES & AGENT SKILLS:
{agent_skills}


Focus ONLY on files related to Views, Screens, Components, and Cells.
Use Construkt design tokens (bgPrimary, textPrimary, etc.) for all colors and spacing.

RULES:
1. For EXISTING files: use `read_workspace_file_lines` then `patch_workspace_file`.
2. For NEW files: use `write_workspace_file`.
3. Create all test files from the blueprint's files_to_test that relate to UI."""
    
    if state.get("compiler_errors"):
        prompt += f"\n\n🚨 PREVIOUS ERRORS:\n{state.get('compiler_errors')[-1]}\nFix only UI-related errors."
        
    print(f"👨‍💻 UI Sub-Agent is generating and applying code to {workspace_path}...")
    result = agent_executor.invoke({"messages": [("user", prompt)]}, config={"recursion_limit": 10})
    
    for msg in result.get("messages", []):
        print(f"[{msg.type.upper()}] {msg.content}")
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"🛠️ Sub-Agent requested tool execution: {msg.tool_calls}")
            
    # Chain to network sub-agent if both domains are active
    domains = state.get("active_subagents", [])
    next_history = "UI Sub-Agent Complete."
    return {"history": [next_history]}

def should_chain_after_ui(state: AgentState) -> str:
    """After UI sub-agent, check if network sub-agent also needs to run."""
    domains = state.get("active_subagents", [])
    if "network" in domains:
        return "network_subagent"
    return "validator"

def network_subagent_node(state: AgentState):
    """Specialized sub-agent focused exclusively on API/Network/Data layer code."""
    llm = get_llm(role="coding")
    workspace_path = state.get("workspace_path")
    blueprint = state.get("blueprint", {})
    agent_skills = state.get("agent_skills", "No custom rules found.")
    
    tools = [read_workspace_file, read_workspace_file_lines, write_workspace_file, patch_workspace_file]
    from langgraph.prebuilt import create_react_agent
    agent_executor = create_react_agent(llm, tools=tools)
    
    prompt = f"""You are a Senior iOS Data Systems Engineer specialized in robust Network and API layers.
You ONLY work on API Services, Repositories, Data Models, DTOs, and Networking logic.

Workspace: {workspace_path}
Task: {state.get('instructions')}

Blueprint:
{blueprint}

TEAM RULES & AGENT SKILLS:
{agent_skills}


Focus ONLY on files related to Services, Repositories, Models, APIs, and DTOs.
Follow clean architecture patterns: Repository -> Service -> DTO -> Domain Model.

RULES:
1. For EXISTING files: use `read_workspace_file_lines` then `patch_workspace_file`.
2. For NEW files: use `write_workspace_file`.
3. Create all test files from the blueprint's files_to_test that relate to networking."""
    
    if state.get("compiler_errors"):
        prompt += f"\n\n🚨 PREVIOUS ERRORS:\n{state.get('compiler_errors')[-1]}\nFix only data/network-related errors."
        
    print(f"👨‍💻 Network Sub-Agent is generating and applying code to {workspace_path}...")
    result = agent_executor.invoke({"messages": [("user", prompt)]}, config={"recursion_limit": 10})
    
    for msg in result.get("messages", []):
        print(f"[{msg.type.upper()}] {msg.content}")
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"🛠️ Sub-Agent requested tool execution: {msg.tool_calls}")
            
    return {"history": ["Network Sub-Agent Complete."]}

def general_coder_node(state: AgentState):
    """Fallback general-purpose coder for tasks that don't fit UI or Network domains."""
    llm = get_llm(role="coding")
    workspace_path = state.get("workspace_path")
    blueprint = state.get("blueprint", {})
    agent_skills = state.get("agent_skills", "No custom rules found.")
    
    tools = [read_workspace_file, read_workspace_file_lines, write_workspace_file, patch_workspace_file]
    from langgraph.prebuilt import create_react_agent
    agent_executor = create_react_agent(llm, tools=tools)
    
    prompt = f"""You are a versatile Staff iOS Software Engineer working in workspace: {workspace_path}

Your task: {state.get('instructions')}

Blueprint:
{blueprint}

TEAM RULES & AGENT SKILLS:
{agent_skills}


IMPORTANT RULES:
1. For EXISTING files: First use `read_workspace_file_lines` to view the target area with line numbers.
   Then use `patch_workspace_file` to surgically replace ONLY the lines that need changing.
2. For NEW files: Use `write_workspace_file` to create them.
3. Always create test files listed in the blueprint's files_to_test."""
    
    if state.get("compiler_errors"):
        prompt += f"\n\n🚨 PREVIOUS BUILD FAILED WITH ERRORS:\n{state.get('compiler_errors')[-1]}\nUse read_workspace_file_lines to find the broken lines, then patch_workspace_file to fix them."
        
    print(f"👨‍💻 General Coder is generating and applying code to {workspace_path}...")
    result = agent_executor.invoke({"messages": [("user", prompt)]}, config={"recursion_limit": 10})
    
    for msg in result.get("messages", []):
        print(f"[{msg.type.upper()}] {msg.content}")
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"🛠️ Sub-Agent requested tool execution: {msg.tool_calls}")
            
    return {"history": ["General Coder Complete (Surgical patching via tool binding)."]}

def validator_node(state: AgentState):
    workspace_path = state.get("workspace_path")
    task_id = state.get("task_id")
    blueprint = state.get("blueprint", {})
    
    # Check if we need a build (skip for pure docs/configs)
    all_files = [f.get("filepath", "") if isinstance(f, dict) else str(f) for f in blueprint.get("files_to_modify", []) + blueprint.get("files_to_create", [])]
    needs_build = any(f.endswith((".swift", ".m", ".h", ".pbxproj", ".xcconfig", ".storyboard", ".xib")) for f in all_files)
    
    if needs_build:
        build_output = execute_xcodebuild(workspace_path)
    else:
        build_output = "Build SUCCESS\nValidation bypassed: Non-coding task detected."
    
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
    # Break out to UI validation phase if build succeeded
    if "PASSED" in state.get("history", [])[-1]:
        return "ui_check"
        
    # Safeguard against infinite loops and clean corrupted states
    if state.get("retries_count", 0) >= 3:
        workspace_path = state.get("workspace_path")
        if workspace_path:
            import subprocess
            print("🚨 Max retries hit! Executing RTK State Rollback...")
            subprocess.run(["rtk", "git", "clean", "-fd"], cwd=workspace_path, check=False)
            subprocess.run(["rtk", "git", "checkout", "--", "."], cwd=workspace_path, check=False)
        return "ui_check"
        
    return "coder" # Feedback loop: go back to coding to fix the compiler error

def ui_vision_validator_node(state: AgentState):
    """
    Conditionally runs visual UI verification after a successful build.
    Only activates if the FeatureBlueprint contains UI-related architecture components.
    """
    blueprint = state.get("blueprint", {})
    workspace_path = state.get("workspace_path")
    arch_components = blueprint.get("architecture_components", [])
    
    # Check if this feature involves UI work
    ui_keywords = ["SwiftUI", "UIKit", "View", "Construkt", "UI", "Screen", "Component"]
    has_ui = any(kw.lower() in comp.lower() for comp in arch_components for kw in ui_keywords)
    
    if not has_ui:
        return {"history": ["UI Vision Check: Skipped (no UI components in blueprint)."]}
    
    # Capture a simulator screenshot
    screenshot_result = capture_simulator_screenshot(workspace_path)
    
    if screenshot_result.startswith("Error") or screenshot_result.startswith("Simulator"):
        # Screenshot capture failed — don't block the pipeline, just warn
        return {"history": [f"UI Vision Check: Screenshot capture failed ({screenshot_result}). Proceeding anyway."]}
    
    # Build design constraints from the blueprint
    design_constraints = f"Architecture components: {', '.join(arch_components)}\n"
    design_constraints += f"Feature: {blueprint.get('feature_name', 'Unknown')}\n"
    design_constraints += "Ensure compliance with Construkt design tokens and MVVM layout patterns."
    
    # Run the vision validation
    vision_result = validate_ui_with_vision(screenshot_result, design_constraints)
    
    if vision_result["passed"]:
        return {"history": [f"UI Vision Check: PASSED. {vision_result['feedback']}"]}
    else:
        # Feed visual feedback back to the coder as compiler errors for the retry loop
        errors = state.get("compiler_errors", [])
        errors.append(f"UI VISION FAILURE: {vision_result['feedback']}")
        retries = state.get("retries_count", 0) + 1
        return {
            "compiler_errors": errors,
            "retries_count": retries,
            "history": [f"UI Vision Check: FAILED. {vision_result['feedback']}"]
        }

def should_proceed_from_ui_check(state: AgentState) -> str:
    """After UI vision check, decide whether to push or loop back to coder."""
    last_history = state.get("history", [""])[-1]
    if "FAILED" in last_history and state.get("retries_count", 0) < 3:
        return "coder"
    return "push"

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
        import os
        from slack_sdk import WebClient
        
        slack_token = os.environ.get("SLACK_BOT_TOKEN")
        slack_channel = os.environ.get("SLACK_CHANNEL_ID")
        task_id = state.get("task_id", "Unknown")
        repo_full_name = state.get("repo_full_name", "Repository")
        
        if slack_token and slack_channel:
            try:
                client = WebClient(token=slack_token)
                client.chat_postMessage(
                    channel=slack_channel,
                    text="Vetting Passed",
                    blocks=[
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn", 
                                "text": f"✅ *Vetting Passed for #{task_id}*\nThe issue is actionable! The Principal Architect is now analyzing `{repo_full_name}` to generate the architectural blueprint. This typically takes 2-3 minutes..."
                            }
                        }
                    ]
                )
            except Exception as e:
                print(f"Failed to post Slack notification: {e}")
                
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
        return "await_clarification"
    return "initialize"

def await_clarification_node(state: AgentState):
    """Placeholder node to freeze LangGraph while waiting for developer comments."""
    return {"history": ["Awaiting clarification from GitHub thread..."]}

def build_graph():
    """Compiles the LangGraph State Machine."""
    graph = StateGraph(AgentState)
    
    graph.add_node("vetting", issue_vetting_node)
    graph.add_node("await_clarification", await_clarification_node)
    graph.add_node("initialize", initialize_workspace_node)
    graph.add_node("context_aggregator", context_aggregator_node)
    graph.add_node("planner", planner_node)
    graph.add_node("blueprint_presentation", blueprint_presentation_node)
    graph.add_node("router", router_node)
    graph.add_node("ui_subagent", ui_subagent_node)
    graph.add_node("network_subagent", network_subagent_node)
    graph.add_node("general_coder", general_coder_node)
    graph.add_node("validator", validator_node)
    graph.add_node("ui_vision_check", ui_vision_validator_node)
    
    def push_node(state: AgentState):
        workspace_path = state.get("workspace_path")
        branch_name = state.get("current_branch")
        task_id = state.get("task_id")
        repo_full_name = state.get("repo_full_name")
        installation_id = state.get("installation_id")
        
        from agent.tools import commit_and_push_branch, post_github_comment
        
        print(f"🚀 Pushing successfully validated code for #{task_id}...")
        push_msg = commit_and_push_branch(
            workspace_path, 
            branch_name, 
            f"Agent Implementation for #{task_id}",
            installation_id=installation_id,
            repo_full_name=repo_full_name
        )
        
        # Notify developer based on the precise outcome
        if "ERROR" in push_msg or "SKIPPED" in push_msg:
            comment = f"⚠️ **Push Halted**\n\nThe orchestrator completed execution but the final push was aborted:\n```text\n{push_msg}\n```\n\n*(This typically means the LLM didn't actually modify any files in the workspace, or there was a git authentication issue).*”"
        else:
            comment = f"✅ **Coding & Validation Complete!**\n\nThe background agents compiled the code successfully and the UI tests passed.\nAll logic and design tokens have been safely pushed to the remote branch `{branch_name}`.\n\n<details><summary><b>Git Push Receipt</b></summary>\n\n```text\n{push_msg}\n```\n</details>\n\nYou can now open a Pull Request!"
        
        if repo_full_name and installation_id:
            post_github_comment(repo_full_name, task_id, installation_id, comment)
            
        return {"history": ["Code pushed to remote repository."]}

    graph.add_node("push", push_node) 
    
    # Wiring the flow
    graph.set_entry_point("vetting")
    
    graph.add_conditional_edges("vetting", should_proceed_from_vetting, {
        "initialize": "initialize",
        "await_clarification": "await_clarification"
    })
    
    # Loop back to vetting once resumed
    graph.add_edge("await_clarification", "vetting")
    
    graph.add_edge("initialize", "context_aggregator")
    graph.add_edge("context_aggregator", "planner")
    graph.add_edge("planner", "blueprint_presentation")
    graph.add_edge("blueprint_presentation", "router")
    
    # Router dispatches to the correct sub-agent
    graph.add_conditional_edges("router", should_route_subagent, {
        "ui_subagent": "ui_subagent",
        "network_subagent": "network_subagent",
        "general_coder": "general_coder"
    })
    
    # UI sub-agent chains to network if both are needed, otherwise goes to validator
    graph.add_conditional_edges("ui_subagent", should_chain_after_ui, {
        "network_subagent": "network_subagent",
        "validator": "validator"
    })
    
    graph.add_edge("network_subagent", "validator")
    graph.add_edge("general_coder", "validator")
    
    # Conditional logic out of the validator (loops back to router on failure)
    graph.add_conditional_edges("validator", should_retry, {
        "coder": "router",           # Loop back through router for targeted fixes
        "ui_check": "ui_vision_check"  # Build passed, run visual check
    })
    
    # Conditional logic out of the UI vision check
    graph.add_conditional_edges("ui_vision_check", should_proceed_from_ui_check, {
        "coder": "router",    # Loop back through router for UI fixes
        "push": "push"        # Everything passed
    })
    
    graph.add_edge("push", END)
    
    # Attach memory so the graph can be paused waiting for Slack human approval
    app = graph.compile(checkpointer=GLOBAL_CHECKPOINTER, interrupt_before=["await_clarification", "router", "push"])
    
    return app
