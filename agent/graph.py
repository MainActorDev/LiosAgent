import os
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END

# Checkpointers are now injected dynamically per-vault

from agent.state import AgentState
from agent.tools import clone_isolated_workspace, post_github_comment, capture_simulator_screenshot, validate_ui_with_vision, fetch_external_link, navigate_to_target_view
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
    
    repo_name = repo_url.split('/')[-1].replace(".git", "") if repo_url else "repo"
    actual_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".workspaces", task_id, repo_name))
    branch_name = f"ios-agent-issue-{task_id}"
    
    return {
        "workspace_path": actual_path,
        "current_branch": branch_name,
        "history": [f"Initialized workspace at {actual_path}"]
    }

async def context_aggregator_node(state: AgentState):
    from agent.mcp_clients import MCPManager
    
    llm = get_llm(role="planning")
    workspace_path = state.get("workspace_path")
    instructions = state.get("instructions", "")
    
    manager = MCPManager()
    tools = await manager.connect_and_get_tools(workspace_path, instructions)
    
    context_parts = []
    
    if not tools:
        print("⚠️ No Serena MCP tools found for Orchestrator. Proceeding with shell fallbacks.")
        context_parts.append("No external MCP tools bounded to python orchestrator.")
    
    if tools:
        try:
            # --- Phase 1: Serena Onboarding (deterministic, no LLM needed) ---
            # Find Serena's onboarding tools by name
            tool_map = {t.name: t for t in tools}
            
            # Check if onboarding was already performed for this project
            if "check_onboarding_performed" in tool_map:
                check_result = await tool_map["check_onboarding_performed"].ainvoke({})
                print(f"🔍 Onboarding check: {str(check_result)[:200]}")
                
                # Run onboarding if not yet performed
                if "onboarding" in tool_map and "not" in str(check_result).lower():
                    print("📋 Running Serena onboarding for first-time project activation...")
                    onboarding_result = await tool_map["onboarding"].ainvoke({})
                    context_parts.append(f"## Serena Onboarding Report\n{onboarding_result}")
                    print(f"✅ Onboarding complete ({len(str(onboarding_result))} chars)")
            
            # Get initial instructions / project context
            if "initial_instructions" in tool_map:
                init_result = await tool_map["initial_instructions"].ainvoke({})
                context_parts.append(f"## Project Context\n{init_result}")
                print(f"✅ Initial instructions loaded ({len(str(init_result))} chars)")
            
            # Get symbols overview for architectural understanding
            if "get_symbols_overview" in tool_map:
                try:
                    symbols_result = await tool_map["get_symbols_overview"].ainvoke({})
                    context_parts.append(f"## Code Structure Overview\n{str(symbols_result)[:4000]}")
                    print(f"✅ Symbols overview loaded")
                except Exception as e:
                    print(f"⚠️ Symbols overview failed: {e}")
            
            # --- Phase 2: LLM-driven external research (only if needed) ---
            # Only spin up the LLM loop if the issue references external systems
            instructions_lower = instructions.lower()
            needs_external = any(kw in instructions_lower for kw in [
                "figma.com", "figma", "atlassian.net", "jira", "http://", "https://"
            ])
            
            if needs_external:
                from langgraph.prebuilt import create_react_agent
                
                # Only include tools relevant for external research
                external_tools = [t for t in tools if t.name in {
                    "query_project", "list_queryable_projects", "fetch_external_link"
                }]
                external_tools.append(fetch_external_link)
                
                if external_tools:
                    agent_executor = create_react_agent(llm, tools=external_tools)
                    prompt = f"""The following issue references external systems. Use your tools to fetch relevant context:
{instructions}

If the issue contains HTTP links, use fetch_external_link to read them.
If the issue mentions Jira, fetch acceptance criteria.
Return a structured markdown report of your findings."""
                    
                    print("🌐 Fetching external references (Figma/Jira/Web)...")
                    result = await agent_executor.ainvoke(
                        {"messages": [("user", prompt)]},
                        config={"recursion_limit": 10}
                    )
                    external_context = result["messages"][-1].content
                    context_parts.append(f"## External References\n{external_context}")
            
        except Exception as e:
            context_parts.append(f"Context gathering error: {e}")
            print(f"⚠️ Context aggregation error: {e}")
        finally:
            await manager.cleanup()
            
    # Fallback to pure shell representation of the file tree so the planner isn't blind
    try:
        import subprocess
        print("🔍 Extracting raw directory tree for the planner...")
        # Ignore obvious noise paths
        tree_output = subprocess.run(
            ["find", ".", "-not", "-path", "*/.*", "-not", "-path", "*/DerivedData/*", "-not", "-path", "*/build/*"],
            cwd=workspace_path, capture_output=True, text=True
        ).stdout
        if tree_output.strip():
            # Cap it to avoid LLM context bloat
            context_parts.append(f"## RAW REPOSITORY TREE\n{tree_output[:8000]}")
    except Exception as e:
        print(f"⚠️ Failed to extract raw file tree: {e}")
        
    # Compile Index of Agent Skills
    agent_skills = ""
    if workspace_path:
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
                    rel_path = os.path.relpath(skill_file, workspace_path)
                    agent_skills += f"- {rel_path}\n"
                
    if not agent_skills.strip():
        agent_skills = "No specific rules found. Follow standard iOS best practices."
    context_data = "\n\n".join(context_parts) if context_parts else "No context gathered."
    
    # --- Ralph Integration: Read cross-task progress log ---
    progress_log = ""
    if workspace_path:
        from agent.tools import read_progress_log
        progress_log = read_progress_log(workspace_path)
        if progress_log:
            context_parts.append(f"## Prior Run Learnings (progress.txt)\n{progress_log[-3000:]}")
            print(f"📖 Loaded {len(progress_log)} chars of cross-task learnings from progress.txt")
    
    return {
        "mcp_context": context_data,
        "agent_skills": agent_skills,
        "progress_log": progress_log,
        "history": ["Context Aggregator Node executed. Serena onboarding + external tools queried."]
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
    
    from agent.vault_manager import VaultManager
    epic_name = state.get("task_id", "default_epic")
    vault_path = VaultManager.create_epic_vault(epic_name)
    VaultManager.save_blueprint(vault_path, blueprint.dict())
    
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
    
    if task_id:
        print(f"✅ Generating Blueprint markdown and posting to GitHub for Task #{task_id}...")
        result = post_github_comment(task_id, md)
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

async def architect_coder_node(state: AgentState):
    """Stateless Node wrapper for the OpenCode autonomous agent runtime."""
    workspace_path = state.get("workspace_path")
    blueprint = state.get("blueprint", {})
    agent_skills = state.get("agent_skills", "No custom rules found.")
    
    prompt = f"""You are a versatile Principal Software Engineer working in workspace: {os.path.abspath(workspace_path)}

Your task: {state.get('instructions')}

Blueprint:
{blueprint}

TEAM RULES & AGENT SKILLS:
The repository maintains documentation and specific architectural guidelines at the following file paths:
{agent_skills}

IMPORTANT RULES:
Before generating code, use your native file-reading tools to investigate any skill files that seem relevant to your current architectural task. Treat their isolated contents as absolute directives.
Solve the task completely, adhering to the design patterns and rules defined above.
Ensure you fulfill every aspect of the blueprint."""
    
    # --- Ralph Integration: Focus on current story if PRD exists ---
    prd_stories = state.get("prd_stories", [])
    if prd_stories:
        from agent.ralph import get_current_story
        current_story = get_current_story(prd_stories)
        if current_story:
            prompt += f"""\n\n📋 CURRENT STORY (focus on THIS only):
Story ID: {current_story['id']}
Title: {current_story['title']}
Description: {current_story['description']}
Acceptance Criteria:
{chr(10).join(f'  - {c}' for c in current_story.get('acceptance_criteria', []))}
Notes: {current_story.get('notes', 'None')}

IMPORTANT: Implement ONLY this story. Do not work on other stories.
After completing, ensure all acceptance criteria are met."""
    
    instructions_lower = state.get('instructions', '').lower()
    has_figma_link = "figma.com" in instructions_lower or "figma" in instructions_lower
    
    if has_figma_link:
        prompt += "\n\n🎨 FIGMA DESIGN LINK DETECTED:\nYou have been provided with the FigmaMCP. You MUST use it to extract the design tokens from the prompt URL, and merge those design rules into the blueprint architecture before writing code."
        
    if state.get("compiler_errors"):
        prompt += f"\n\n🚨 PREVIOUS BUILD FAILED WITH ERRORS:\n{state.get('compiler_errors')[-1]}\nDiagnose and fix these specific compilation errors."
        
    print(f"👨‍💻 Architect Coder is farming execution to OpenCode in {workspace_path}...")
    
    import subprocess
    import sys
    import json
    import re
    
    # 1. Enforce strict configuration by writing a local opencode.json
    opencode_config = {
        "permission": {
            "bash": {
                "rm *": "deny",     # Strictly block deletions as requested
                "*": "ask"
            },
            "edit": {
                "*": "allow"
            }
        }
    }
    
    opencode_config["mcp"] = {}
    
    # Dynamically inject XcodeBuildMCP so the LLM can construct native compilation schemas
    opencode_config["mcp"]["XcodeBuildMCP"] = {
        "type": "local",
        "command": ["npx", "-y", "xcodebuildmcp"],
        "enabled": True
    }
    print("🛠️ Architect Coder natively mounting XcodeBuildMCP into OpenCode sandbox...")
    
    if has_figma_link and os.environ.get("FIGMA_ACCESS_TOKEN"):
        opencode_config["mcp"]["FigmaMCP"] = {
            "type": "local",
            "command": ["npx", "-y", "github:glips/figma-context-mcp"],
            "enabled": True,
            "env": {
                "FIGMA_ACCESS_TOKEN": os.environ.get("FIGMA_ACCESS_TOKEN")
            }
        }
        print("🎨 Architect Coder natively mounting FigmaMCP into OpenCode sandbox...")
        
    config_path = os.path.join(workspace_path, "opencode.json")
    with open(config_path, "w") as f:
        json.dump(opencode_config, f, indent=2)
        
    cmd = ["npx", "--yes", "opencode-ai", "run", prompt, "--dangerously-skip-permissions"]
    
    # 2. Resume session if recovering from PR context
    session_id = state.get("opencode_session_id")
    if session_id:
        cmd.extend(["--continue", "--session", session_id])
        print(f"🔄 Resuming OpenCode Session {session_id} for PR feedback loop...")
        
    # 3. Stream real-time output and harvest Session ID
    print(f"👨‍💻 Architect Coder is farming execution to OpenCode in {workspace_path} (Auto-Approve Enabled)...")
    process = subprocess.Popen(
        cmd,
        cwd=workspace_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Merge stderr into stdout
        text=True,
        bufsize=1
    )
    
    captured_output = []
    
    for line in iter(process.stdout.readline, ''):
        # Print natively bypassing python typical buffering
        sys.stdout.write(line)
        sys.stdout.flush()
        captured_output.append(line)
        
    process.wait()
    
    # 4. Extract Session ID if available in TUI raw output
    full_output = "".join(captured_output)
    session_match = re.search(r"Session\s*ID\s*[:=]\s*([a-zA-Z0-9_-]+)", full_output, re.IGNORECASE)
    
    history_msg = "OpenCode execution complete."
    extracted_session = session_id
    if session_match:
        extracted_session = session_match.group(1)
        history_msg += f" (Session ID cached: {extracted_session})"
        
    return {"history": [history_msg], "opencode_session_id": extracted_session}

def post_approval_to_slack(task_id: str, success: bool, feedback: str = ""):
    slack_channel = os.environ.get("SLACK_CHANNEL_ID")
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    if slack_channel and bot_token:
        from slack_sdk import WebClient
        client = WebClient(token=bot_token)
        try:
            status_emoji = "✅" if success else "❌"
            
            is_fatal = "FATAL" in feedback.upper() or "BUILD FAILED" in feedback.upper() or "ERROR:" in feedback.upper()
            
            if success:
                status_text = "All compilation and UI validations have passed! Would you like me to push this code?"
            elif is_fatal:
                status_text = f"Critical Simulator Failure:\n_{feedback}_\n\nThe workspace was rolled back to prevent pushing broken code."
            else:
                status_text = f"UI Validation FAILED:\n_{feedback}_\n\nWould you like to manually approve and push this code anyway?"
            
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"{status_emoji} *AI Validation for Task #{task_id}*\n {status_text}"}
                }
            ]
            
            # Only offer the manual override button for subjective visual mismatches, NOT hard compile crashes
            if success or not is_fatal:
                blocks.append({
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
                })
                
            client.chat_postMessage(
                channel=slack_channel,
                text=f"Validation Result for Task {task_id}",
                blocks=blocks
            )
        except Exception as e:
            print(f"Failed to post Slack approval: {e}")

def validator_node(state: AgentState):
    workspace_path = state.get("workspace_path")
    task_id = state.get("task_id")
    blueprint = state.get("blueprint", {})
    
    # Import the newly restored build logic
    from agent.tools import execute_xcodebuild
    
    # Check if we need a build (skip for pure docs/configs)
    all_files = [f.get("filepath", "") if isinstance(f, dict) else str(f) for f in blueprint.get("files_to_modify", []) + blueprint.get("files_to_create", [])]
    needs_build = any(f.endswith((".swift", ".m", ".h", ".pbxproj", ".xcconfig", ".storyboard", ".xib")) for f in all_files)
    
    if needs_build:
        print(f"🔧 Compiling Workspace {task_id} via xcodebuild (This may take several minutes)...")
        build_output = execute_xcodebuild(workspace_path)
    else:
        print(f"⏭️ Validation bypassed: Non-coding task detected for Task {task_id}.")
        build_output = "Build SUCCESS\nValidation bypassed: Non-coding task detected."
    
    if "Build SUCCESS" in build_output:
        return {"history": ["Xcode Build Validation PASSED! Proceeding to Visual Evaluation..."]}
    else:
        errors = state.get("compiler_errors", [])
        errors.append(build_output)
        retries = state.get("retries_count", 0) + 1
        story_retries = state.get("story_retries_count", 0) + 1
        return {
            "compiler_errors": errors,  
            "retries_count": retries,
            "story_retries_count": story_retries,
            "history": [f"Xcode Build Failed. Retry count: {retries} (Story retries: {story_retries})"]
        }

def maestro_navigation_generator_node(state: AgentState):
    """
    Hierarchy-aware navigation: after the app is launched and a screenshot is captured,
    this node uses Maestro's live accessibility hierarchy to guide navigation
    step-by-step to the target view using real element labels (never hallucinated).
    
    This node runs BETWEEN capture_simulator_screenshot and validate_ui_with_vision.
    It re-captures the screenshot after navigation completes.
    """
    blueprint = state.get("blueprint", {})
    workspace_path = state.get("workspace_path")
    instructions = state.get("instructions", "")
    
    files = blueprint.get("files_to_modify", []) + blueprint.get("files_to_create", [])
    has_ui = any(str(f.get("filepath", "")).endswith(".swift") for f in files)
    
    if not has_ui:
        return {"history": ["Maestro Navigation: Skipped (no Swift files touched)."]}
    
    # Get the device info from the previous capture step
    device_udid = state.get("device_udid", "")
    bundle_id = state.get("bundle_id", "")
    
    if not device_udid or not bundle_id:
        print("⚠️ Maestro Navigation: No device/bundle info from capture step, skipping.")
        return {"history": ["Maestro Navigation: Skipped (no device info available)."]}
    
    print(f"🤖 Running hierarchy-aware Maestro navigation...")
    from agent.tools import get_maestro_bin
    import subprocess
    import re
    
    maestro_flow = os.path.join(workspace_path, "maestro_flow.yaml")
    
    # ─── Feature: Human Override Detection ───
    # If the developer provides a Maestro snippet in the GitHub Issue, bypass the Vision LLM entirely
    override_match = re.search(r'```(?:yaml)?\s*(appId:.*?)\s*```', instructions, re.DOTALL | re.IGNORECASE)
    
    if override_match:
        print("🛠️ Human developer provided direct Maestro YAML override! Bypassing Vision LLM.")
        raw_override = override_match.group(1).strip()
        
        # Invisibly inject the video telemetry hooks so the human still gets a beautiful validation MP4
        if "startRecording:" not in raw_override and "---" in raw_override:
            parts = raw_override.split("---", 1)
            raw_override = f"{parts[0]}---\n- startRecording: lios_navigation{parts[1]}"
            if "stopRecording" not in raw_override:
                raw_override += "\n\n- takeScreenshot: lios_final_state\n- stopRecording\n"
                
        with open(maestro_flow, "w") as f:
            f.write(raw_override)
            
        nav_log = ["Bypassed Vision LLM: Using human-provided Maestro YAML flow from issue description."]
    else:
        nav_log = navigate_to_target_view(device_udid, workspace_path, bundle_id, instructions, blueprint)
    
    # After navigation, we have an intelligent maestro_flow.yaml. Let's run it linearly to capture 
    # the clean video and final screenshot for the UI Validation!
    maestro_flow = os.path.join(workspace_path, "maestro_flow.yaml")
    
    video_path = ""
    screenshot_path = state.get("screenshot_path", "")
    
    if os.path.exists(maestro_flow):
        with open(maestro_flow, "r") as f:
            content = f.read()
        
        # Only run it if it's the valid synthesized YAML, not the generic "no navigation needed" comment
        if content.startswith("appId:"):
            print("🎥 Executing clean synthesized Maestro navigation for final PR video...")
            import time
            maestro_bin = get_maestro_bin()
            subprocess.run([maestro_bin, "--device", device_udid, "test", maestro_flow], check=False, cwd=workspace_path)
            
            # The YAML saves `lios_navigation.mp4` and `lios_final_state.png` cleanly to the working directory
            if os.path.exists(os.path.join(workspace_path, "lios_navigation.mp4")):
                video_path = "lios_navigation.mp4"
            if os.path.exists(os.path.join(workspace_path, "lios_final_state.png")):
                screenshot_path = "lios_final_state.png"
            
            time.sleep(4)  # Let animations and background video encoders complete
        else:
            # If no Maestro flow was needed, just re-take a normal screenshot
            full_path = os.path.join(workspace_path, screenshot_path) if not os.path.isabs(screenshot_path) else screenshot_path
            subprocess.run(["xcrun", "simctl", "io", device_udid, "screenshot", full_path], check=False, capture_output=True)
            subprocess.run(["sips", "-Z", "800", full_path], check=False, capture_output=True)
    
    log_summary = "; ".join(nav_log) if nav_log else "No navigation needed."
    return {
        "video_path": video_path,
        "screenshot_path": screenshot_path,
        "history": [f"Maestro Navigation: {log_summary}"]
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
        return "push"
        
    return "coder" # Feedback loop: go back to coding to fix the compiler error

def ui_vision_validator_node(state: AgentState):
    """
    Conditionally runs visual UI verification after a successful build.
    Only activates if the FeatureBlueprint contains UI-related architecture components.
    """
    blueprint = state.get("blueprint", {})
    workspace_path = state.get("workspace_path")
    arch_components = blueprint.get("architecture_components", [])
    
    # We now universally run vision tests if ANY Swift file was modified, avoiding brittle architecture keyword mismatches
    files = blueprint.get("files_to_modify", []) + blueprint.get("files_to_create", [])
    has_ui = any(str(f.get("filepath", "")).endswith(".swift") for f in files)
    
    print(f"📱 UI Vision Check evaluation initialized...")
    
    if not has_ui:
        print("⏭️ UI Vision Check Skipped: No Swift source files were modified in this blueprint.")
        post_approval_to_slack(state.get("task_id", "Unknown"), success=True)
        return {"history": ["UI Vision Check: Skipped (no Swift files touched)."]}
    
    task_id = state.get("task_id", "default_task")
    print("📸 Booting Simulator and waiting for view to flush pixels...")
    screenshot_result = capture_simulator_screenshot(workspace_path, str(task_id))
    
    if "error" in screenshot_result:
        print(f"⚠️ Screenshot capture failed. Aborting Vision Check: {screenshot_result['error']}")
        
        post_approval_to_slack(state.get("task_id", "Unknown"), success=False, feedback=screenshot_result['error'])
        
        return {
            "screenshot_path": "",
            "device_udid": "",
            "bundle_id": "",
            "history": [f"UI Vision Check: FATAL ERROR. {screenshot_result['error']}"]
        }
    
    filename = os.path.basename(screenshot_result.get("screenshot_path", ""))
    
    # Store device info + initial screenshot in state for the maestro navigation node
    # The maestro node will navigate and re-capture, then vision runs after
    return {
        "screenshot_path": filename,
        "device_udid": screenshot_result.get("device_udid", ""),
        "bundle_id": screenshot_result.get("bundle_id", ""),
        "history": [f"Simulator booted and initial screenshot captured: {filename}"]
    }

def vision_validation_node(state: AgentState):
    """
    Runs the actual Multimodal Vision LLM check against the (post-navigation) screenshot.
    This is the final validation gate before the push approval.
    """
    blueprint = state.get("blueprint", {})
    workspace_path = state.get("workspace_path")
    screenshot_path = state.get("screenshot_path", "")
    
    if not screenshot_path:
        post_approval_to_slack(state.get("task_id", "Unknown"), success=True)
        return {"history": ["Vision Validation: Skipped (no screenshot available)."]}
    
    full_path = os.path.join(workspace_path, screenshot_path) if not os.path.isabs(screenshot_path) else screenshot_path
    
    arch_components = blueprint.get("architecture_components", [])
    design_constraints = f"Architecture components: {', '.join(arch_components)}\n"
    design_constraints += f"Feature: {blueprint.get('feature_name', 'Unknown')}\n"
    design_constraints += "Ensure compliance with Construkt design tokens and MVVM layout patterns."
    
    print(f"🤖 Sending post-navigation snapshot to Vision LLM...")
    vision_result = validate_ui_with_vision(full_path, design_constraints)
    
    if vision_result["passed"]:
        print(f"✅ UI Vision PASSED: {vision_result['feedback']}")
        post_approval_to_slack(state.get("task_id", "Unknown"), success=True)
        return {"history": [f"UI Vision Check: PASSED. {vision_result['feedback']}"]}
    else:
        print(f"❌ UI Vision FAILED: {vision_result['feedback']}")
        post_approval_to_slack(state.get("task_id", "Unknown"), success=False, feedback=vision_result['feedback'])
        return {"history": [f"UI Vision Check: FAILED. {vision_result['feedback']}"]}

def should_proceed_from_ui_check(state: AgentState) -> str:
    """After UI vision check, unconditionally proceed to the push gate so the human can decide."""
    return "push"

def issue_vetting_node(state: AgentState):
    llm = get_llm(role="planning")
    instructions = state.get("instructions", "")
    
    prompt = f"""You are the gateway filter for an advanced iOS Agentic Coder. 
Review the following GitHub Issue:
{instructions}

You have access to powerful downstream MCP tools that can natively parse Figma links, Jira tickets, and codebase structure.
If the issue contains ANY external links (like `figma.com` or `atlassian.net`), OR mentions a clear bug, feature, or UI request, simply reply 'ACTIONABLE'.
Only reply with a polite comment asking for clarification if the issue is literal garbage text, single keywords without context (e.g. "dummy message", "hello world", "test"), or completely empty. Do NOT write 'ACTIONABLE' in this case.
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
        if task_id:
            post_github_comment(task_id, response)
            
        return {"history": ["Issue Vetting: Failed. Commented on GitHub and halted."]}

def should_proceed_from_vetting(state: AgentState) -> str:
    if "halted." in state.get("history", [""])[-1]:
        return "await_clarification"
    return "initialize"

def await_clarification_node(state: AgentState):
    """Placeholder node to freeze LangGraph while waiting for developer comments."""
    return {"history": ["Awaiting clarification from GitHub thread..."]}

def blueprint_approval_gate(state: AgentState):
    """Placeholder node to safely pause execution for human Blueprint Review. State dict is dynamically patched by main.py upon resume."""
    return {}

def should_proceed_from_blueprint(state: AgentState) -> str:
    """Dynamically routes execution depending on whether the user approved the blueprint or issued feedback."""
    last_history = state.get("history", [""])[-1]
    
    if "approved by human" in last_history:
        return "prd_decomposer"
    elif "Blueprint feedback received" in last_history:
        return "planner"
        
    return "prd_decomposer"

def prd_decomposer_node(state: AgentState):
    """
    Ralph Integration: Decomposes the approved FeatureBlueprint into
    atomic user stories for sequential execution.
    """
    from agent.ralph import decompose_blueprint_to_stories, format_stories_for_github
    
    blueprint = state.get("blueprint", {})
    instructions = state.get("instructions", "")
    mcp_context = state.get("mcp_context", "")
    progress_log = state.get("progress_log", "")
    
    print("📋 Decomposing blueprint into atomic user stories (Ralph PRD)...")
    stories = decompose_blueprint_to_stories(
        blueprint, instructions, mcp_context, progress_log
    )
    
    print(f"📋 Generated {len(stories)} user stories:")
    from agent.vault_manager import VaultManager
    epic_name = state.get("task_id", "default_epic")
    
    for s in stories:
        print(f"  → {s['id']}: {s['title']} (priority: {s['priority']})")
        # Physically generate the Story Vault
        story_path = VaultManager.create_story_vault(epic_name, s["id"])
        with open(os.path.join(story_path, "story_plan.md"), "w") as f:
            f.write(f"# {s['id']}: {s['title']}\n\n{s['description']}\n\n## Acceptance Criteria\n")
            for c in s.get("acceptance_criteria", []):
                f.write(f"- [ ] {c}\n")
            if s.get("notes"):
                f.write(f"\n## Notes\n{s['notes']}")

    
    # Post the decomposition to GitHub for visibility
    repo_full_name = state.get("repo_full_name")
    task_id = state.get("task_id")
    installation_id = state.get("installation_id")
    
    if task_id:
        from agent.tools import post_github_comment
        feature_name = blueprint.get("feature_name", "Feature")
        md = format_stories_for_github(stories, feature_name)
        post_github_comment(task_id, md)
    
    return {
        "prd_stories": stories,
        "current_story_index": 0,
        "history": [f"PRD Decomposition complete: {len(stories)} stories generated."]
    }

def story_selector_node(state: AgentState):
    """Pick the next pending story from the PRD, or signal completion."""
    from agent.ralph import get_current_story
    
    stories = state.get("prd_stories", [])
    current_story = get_current_story(stories)
    
    if current_story:
        print(f"📖 Next story: {current_story['id']} - {current_story['title']}")
        return {
            "current_story_id": current_story["id"],
            "story_retries_count": 0,   # Reset per-story retry counter
            "compiler_errors": [],       # Clear errors from previous story
            "history": [f"Story selector: picked {current_story['id']} - {current_story['title']}"]
        }
    else:
        completed = state.get("completed_story_ids", [])
        skipped = state.get("skipped_story_ids", [])
        print(f"🎉 All stories processed! Completed: {len(completed)}, Skipped: {len(skipped)}")
        return {
            "current_story_id": "",
            "history": [f"All stories processed. {len(completed)} completed, {len(skipped)} skipped."]
        }

def story_commit_node(state: AgentState):
    """Commit the current story's changes after a successful build."""
    from agent.tools import commit_story
    from agent.ralph import mark_story_passed
    
    workspace_path = state.get("workspace_path")
    stories = state.get("prd_stories", [])
    story_id = state.get("current_story_id", "")
    
    # Find the current story
    current_story = next((s for s in stories if s["id"] == story_id), None)
    if not current_story:
        return {"history": [f"Story commit: story {story_id} not found in PRD."]}
    
    result = commit_story(workspace_path, current_story)
    print(f"  📦 {result}")
    
    # Mark story as passed
    updated_stories = mark_story_passed(stories, story_id)
    completed = state.get("completed_story_ids", [])
    completed.append(story_id)
    
    return {
        "prd_stories": updated_stories,
        "completed_story_ids": completed,
        "history": [f"Story {story_id} committed: {result}"]
    }

def story_progress_node(state: AgentState):
    """Append progress.txt entry for the completed story."""
    from agent.tools import append_story_progress
    
    workspace_path = state.get("workspace_path")
    stories = state.get("prd_stories", [])
    story_id = state.get("current_story_id", "")
    
    current_story = next((s for s in stories if s["id"] == story_id), None)
    if current_story:
        append_story_progress(workspace_path, current_story, success=True)
    
    return {"history": [f"Progress logged for story {story_id}."]}

def story_skip_node(state: AgentState):
    """Skip a story that failed too many times, log it, and move on."""
    from agent.tools import append_story_progress
    
    workspace_path = state.get("workspace_path")
    stories = state.get("prd_stories", [])
    story_id = state.get("current_story_id", "")
    
    current_story = next((s for s in stories if s["id"] == story_id), None)
    
    # Log the failure
    if current_story:
        build_errors = state.get("compiler_errors", [])
        last_error = build_errors[-1] if build_errors else ""
        append_story_progress(workspace_path, current_story, success=False, 
                             build_output=last_error)
        current_story["notes"] = f"SKIPPED after 3 retries. Last error: {last_error[-200:]}"
    
    skipped = state.get("skipped_story_ids", [])
    skipped.append(story_id)
    
    # Git rollback: discard uncommitted changes from the failed story
    import subprocess
    subprocess.run(["git", "checkout", "--", "."], cwd=workspace_path, 
                   check=False, capture_output=True)
    subprocess.run(["git", "clean", "-fd"], cwd=workspace_path, 
                   check=False, capture_output=True)
    
    print(f"  ⏭️ Skipped story {story_id} after 3 failed attempts.")
    
    return {
        "prd_stories": stories,
        "skipped_story_ids": skipped,
        "story_retries_count": 0,
        "compiler_errors": [],
        "history": [f"Story {story_id} SKIPPED after max retries. Rolled back uncommitted changes."]
    }

def should_retry_story(state: AgentState) -> str:
    """Per-story retry logic. Replaces the global should_retry."""
    last_history = state.get("history", [""])[-1]
    
    # Build succeeded → commit this story
    if "PASSED" in last_history:
        return "story_commit"
    
    # Per-story retry limit
    if state.get("story_retries_count", 0) >= 3:
        return "story_skip"
    
    # Retry: send back to coder with error context
    return "coder"

def should_continue_stories(state: AgentState) -> str:
    """After story_selector picks a story, route based on whether there's work left."""
    if state.get("current_story_id"):
        return "architect_coder"
    return "ui_check"

def build_graph(checkpointer=None):
    """Compiles the LangGraph State Machine."""
    graph = StateGraph(AgentState)
    
    graph.add_node("vetting", issue_vetting_node)
    graph.add_node("await_clarification", await_clarification_node)
    graph.add_node("initialize", initialize_workspace_node)
    graph.add_node("context_aggregator", context_aggregator_node)
    graph.add_node("planner", planner_node)
    graph.add_node("blueprint_presentation", blueprint_presentation_node)
    graph.add_node("blueprint_approval_gate", blueprint_approval_gate)
    graph.add_node("prd_decomposer", prd_decomposer_node)
    graph.add_node("story_selector", story_selector_node)
    graph.add_node("story_commit", story_commit_node)
    graph.add_node("story_progress", story_progress_node)
    graph.add_node("story_skip", story_skip_node)
    graph.add_node("architect_coder", architect_coder_node)
    graph.add_node("validator", validator_node)
    graph.add_node("ui_vision_check", ui_vision_validator_node)        # Stage 1: Boot, build, capture initial screenshot
    graph.add_node("maestro_navigation_generator", maestro_navigation_generator_node)  # Stage 2: Navigate to target view
    graph.add_node("vision_validation", vision_validation_node)        # Stage 3: Run Vision LLM check
    
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
            f"Agent Implementation for #{task_id}"
        )
        
        # Notify developer based on the precise outcome
        if "ERROR" in push_msg or "SKIPPED" in push_msg:
            # Extract actual crash logs from state
            err_details = ""
            compiler_errors = state.get("compiler_errors", [])
            last_hist = state.get("history", [""])[-1]
            
            if compiler_errors:
                caps = str(compiler_errors[-1])
                err_details = f"\n\n**🛑 Compiler / Build Crash:**\n```text\n{caps[-1500:]}\n```"
            elif "FATAL" in last_hist or "ERROR" in last_hist.upper():
                err_details = f"\n\n**🛑 Pipeline Crash:**\n```text\n{last_hist}\n```"
                
            comment = f"⚠️ **Push Halted**\n\nThe orchestrator encountered a critical bottleneck and aborted the execution branch:\n```text\n{push_msg}\n```"
            comment += err_details
            comment += "\n\n💡 *Tip: You can reply directly to this comment (e.g. `Redo: use a VStack instead`) to revive this workflow and try again!*"
        else:
            last_hist = state.get("history", [""])[-1]
            if "UI Vision Check: FAILED" in last_hist:
                comment = f"⚠️ **Partial Success (Code Pushed, Vision Failed)**\n\nThe background agents compiled the code successfully and the architecture modifications have been safely pushed to `{branch_name}`. However, the autonomous Maestro UI Validation failed or timed out:\n\n```text\n{last_hist}\n```\n\n*Please manually verify the visual logic below:*\n"
            else:
                comment = f"✅ **Coding & Validation Complete!**\n\nThe background agents compiled the code successfully and the UI tests passed.\nAll logic and design tokens have been safely pushed to the remote branch `{branch_name}`.\n"
            
            # Explicitly render identical visual context into the PR for humans!
            rendered_shot = state.get("screenshot_path")
            if rendered_shot:
                comment += "\n### 📱 Simulator UX Snapshot\n"
                comment += f'<img src="https://raw.githubusercontent.com/{repo_full_name}/{branch_name}/{rendered_shot}" width="300" alt="Simulator Capture" />\n'
                
            rendered_video = state.get("video_path", "")
            if rendered_video:
                comment += "\n### 🎥 UI Traversal Telemetry\n"
                comment += f'Watch the Maestro AI execution:\n\nhttps://github.com/{repo_full_name}/raw/{branch_name}/{rendered_video}\n'
                
            comment += f"\n<details><summary><b>Git Push Receipt</b></summary>\n\n```text\n{push_msg}\n```\n</details>\n\n### 🚀 [Click here to quickly open a Pull Request!](https://github.com/{repo_full_name}/compare/{branch_name}?expand=1)"
        
        if task_id:
            post_github_comment(task_id, comment)
            
        # Intelligent garbage collection:
        # If the push successfully merged to the cloud, there is no reason to hoard 300MB of local Xcode/SPM build caches.
        # But if it failed, we MUST leave it on disk for the human engineer to `cd` into and forensically investigate.
        if "ERROR" not in push_msg and "SKIPPED" not in push_msg:
            # --- Ralph Integration: Write learnings to progress.txt + AGENTS.md ---
            from agent.tools import write_progress_log
            try:
                write_progress_log(
                    workspace_path, 
                    task_id, 
                    state.get("instructions", ""),
                    state.get("blueprint", {}),
                    state.get("history", [])
                )
                print("📝 Progress log and AGENTS.md updated with learnings.")
            except Exception as e:
                print(f"⚠️ Progress log write failed (non-fatal): {e}")

            import shutil
            import os
            try:
                if os.path.exists(workspace_path):
                    container_path = os.path.dirname(workspace_path)
                    shutil.rmtree(container_path, ignore_errors=True)
                    print(f"🧹 Auto-destructed workspace container {container_path} to reclaim disk space.")
            except Exception as e:
                print(f"Failed to auto-destruct workspace: {e}")
            
            return {"history": ["Code pushed to remote repository and sandbox garbage collected."], "halted": False}
        else:
            return {"history": ["Push aborted or skipped. Workflow halted."], "halted": True, "retries_count": 0}

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
    
    # Send presentation to approval gate
    graph.add_edge("blueprint_presentation", "blueprint_approval_gate")
    
    # Dynamically route: either loop back to planner with feedback, or proceed to execution
    graph.add_conditional_edges("blueprint_approval_gate", should_proceed_from_blueprint, {
        "planner": "planner",
        "prd_decomposer": "prd_decomposer"
    })
    
    # --- Phase 3: Ralph Loop Edges ---
    
    # PRD decomposer feeds into story selector
    graph.add_edge("prd_decomposer", "story_selector")
    
    # Story selector: either pick a story to work on, or all done → UI check
    graph.add_conditional_edges("story_selector", should_continue_stories, {
        "architect_coder": "architect_coder",
        "ui_check": "ui_vision_check"
    })
    
    # Coder → Validator
    graph.add_edge("architect_coder", "validator")
    
    # Validator: per-story retry or commit
    graph.add_conditional_edges("validator", should_retry_story, {
        "coder": "architect_coder",
        "story_commit": "story_commit",
        "story_skip": "story_skip"
    })
    
    # After commit: log progress, then loop back to story selector
    graph.add_edge("story_commit", "story_progress")
    graph.add_edge("story_progress", "story_selector")
    
    # After skip: loop back to story selector for next story
    graph.add_edge("story_skip", "story_selector")
    
    # --- Post-loop: UI Vision Pipeline ---
    graph.add_edge("ui_vision_check", "maestro_navigation_generator")
    graph.add_edge("maestro_navigation_generator", "vision_validation")
    
    # Vision validation always proceeds to push gate (no auto-loop)
    graph.add_conditional_edges("vision_validation", should_proceed_from_ui_check, {
        "coder": "architect_coder",    # Reserved but currently unused
        "push": "push"                # Always goes here
    })
    
    def should_proceed_from_push(state: AgentState):
        """Dynamically route successful runs to END, but trap failed runs to allow GitHub comments to revive them with 'Redo'"""
        from langgraph.graph import END
        if state.get("halted", False):
            return "await_clarification"
        return END

    graph.add_conditional_edges("push", should_proceed_from_push, {
        "await_clarification": "await_clarification",
        "__end__": END
    })
    
    # Attach memory so the graph can be paused waiting for human approval
    # We now pause at blueprint_approval_gate instead of architect_coder to prevent deadlock during retries
    app = graph.compile(checkpointer=checkpointer, interrupt_before=["await_clarification", "blueprint_approval_gate", "push"])
    
    return app
