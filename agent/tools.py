import os
import subprocess
import shutil
import requests
from typing import Optional
from langchain_core.tools import tool

# Base directory for isolated Git work
BASE_WORKSPACE_DIR = os.path.join(os.path.dirname(__file__), "..", ".workspaces")

def _ensure_workspaces_dir():
    if not os.path.exists(BASE_WORKSPACE_DIR):
        os.makedirs(BASE_WORKSPACE_DIR)

def clone_isolated_workspace(task_id: str, repo_url: str) -> str:
    """
    Maintains a single warm 'seed_cache' repo for hyper-fast APFS cloning.
    Instantly duplicates this seed into the task workspace.
    """
    _ensure_workspaces_dir()
    # Create a unique, URL-safe cache directory for this specific repository
    import hashlib
    repo_hash = hashlib.md5(repo_url.encode()).hexdigest()[:8]
    seed_name = f"seed_cache_{repo_hash}"
    
    seed_path = os.path.join(BASE_WORKSPACE_DIR, seed_name)
    
    repo_name = repo_url.split('/')[-1].replace(".git", "") if repo_url else "repo"
    container_path = os.path.join(BASE_WORKSPACE_DIR, task_id)
    workspace_path = os.path.join(container_path, repo_name)
    
    try:
        # 1. Maintain the Repo-Specific Seed Cache
        if not os.path.exists(seed_path):
            subprocess.run(["git", "clone", repo_url, seed_path], check=True, capture_output=True)
        else:
            # Allow developers to explicitly override the remote base branch via environment configuration
            target_branch = os.environ.get("TARGET_BRANCH")
            if not target_branch:
                # Dynamically fetch the default primary branch that the seed cache was originally cloned into
                branch_res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=seed_path, capture_output=True, text=True)
                target_branch = branch_res.stdout.strip() if branch_res.stdout else "main"
            
            subprocess.run(["git", "reset", "--hard"], cwd=seed_path, check=True, capture_output=True)
            subprocess.run(["git", "checkout", target_branch], cwd=seed_path, check=True, capture_output=True)
            subprocess.run(["git", "pull"], cwd=seed_path, check=True, capture_output=True)

        # 2. Instantly replicate the directory using macOS APFS Copy-on-Write
        if os.path.exists(workspace_path):
            shutil.rmtree(workspace_path)
            
        os.makedirs(container_path, exist_ok=True)
            
        try:
            subprocess.run(["cp", "-cR", seed_path, workspace_path], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            subprocess.run(["cp", "-R", seed_path, workspace_path], check=True) # Fallback
            
        # 3. Check out the agent's branch (using -B to overwrite safely if it already exists)
        branch_name = f"ios-agent-issue-{task_id}"
        subprocess.run(["git", "checkout", "-B", branch_name], cwd=workspace_path, check=True, capture_output=True)
        
        # 4. Strictly ignore execution payloads to prevent token leakage
        gitignore_path = os.path.join(workspace_path, ".gitignore")
        with open(gitignore_path, "a") as f:
            f.write("\n# Lios-Agent Execution Payloads\nopencode.json\n")
            
        return f"Hot Workspace cloned via APFS at: {workspace_path}"
    except subprocess.CalledProcessError as e:
        return f"Error during workspace prep: {e.stderr}"



def prepare_project_structure(workspace_path: str):
    use_rtk = shutil.which("rtk") is not None
    
    if os.path.exists(os.path.join(workspace_path, "project.yml")):
        cmd = ["rtk", "xcodegen", "generate"] if use_rtk else ["xcodegen", "generate"]
        subprocess.run(cmd, cwd=workspace_path, check=False)
    elif os.path.exists(os.path.join(workspace_path, "Tuist", "Project.swift")):
        cmd = ["rtk", "tuist", "generate"] if use_rtk else ["tuist", "generate"]
        subprocess.run(cmd, cwd=workspace_path, check=False)
    elif os.path.exists(os.path.join(workspace_path, "Package.swift")):
        cmd = ["rtk", "swift", "package", "resolve"] if use_rtk else ["swift", "package", "resolve"]
        subprocess.run(cmd, cwd=workspace_path, check=False)

def execute_xcodebuild(workspace_path: str) -> str:
    prepare_project_structure(workspace_path)
    
    use_rtk = shutil.which("rtk") is not None
    
    # Determine the most accurate build scheme natively
    try:
        list_res = subprocess.run(["xcodebuild", "-list"], cwd=workspace_path, capture_output=True, text=True)
        schemes = []
        in_schemes = False
        for line in list_res.stdout.split('\n'):
            if "Schemes:" in line:
                in_schemes = True
                continue
            if in_schemes:
                if not line.strip(): break
                schemes.append(line.strip())
        
        # Filter test suites and resolve best target
        app_schemes = [s for s in schemes if not s.endswith('Tests') and not s.endswith('Testing') and not "Preview" in s]
        chosen_scheme = app_schemes[0] if app_schemes else (schemes[0] if schemes else "App")
    except Exception:
        chosen_scheme = "App"
        
    print(f"🎯 Resolved workspace target scheme: {chosen_scheme}")
    
    # Fallback to pure xcodebuild if no custom fast-build script exists
    if use_rtk:
        build_cmd = ["rtk", "xcodebuild", "build", "-scheme", chosen_scheme, "-destination", "generic/platform=iOS Simulator"]
    else:
        build_cmd = ["xcodebuild", "build", "-scheme", chosen_scheme, "-destination", "generic/platform=iOS Simulator"]
    
    if os.path.exists(os.path.join(workspace_path, "scripts", "xcodebuild_cached.sh")):
        if use_rtk:
            build_cmd = ["rtk", "bash", "./scripts/xcodebuild_cached.sh"]
        else:
            build_cmd = ["bash", "./scripts/xcodebuild_cached.sh"]
        
    try:
        # We use cwd=workspace_path so xcodebuild runs in the correct directory context
        result = subprocess.run(
            build_cmd,
            cwd=workspace_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return f"Build SUCCESS!\n\nOutput:\n{result.stdout[-2000:] if not use_rtk else result.stdout}"
        else:
            return f"Build FAILED!\n\nError Log:\n{result.stderr[-2000:] if not use_rtk else result.stderr}\n\nStdout:\n{result.stdout[-2000:] if not use_rtk else result.stdout}"
            
    except Exception as e:
        return f"Failed to execute build script: {str(e)}"

def commit_and_push_branch(workspace_path: str, branch_name: str, commit_message: str, installation_id: str = None, repo_full_name: str = None) -> str:
    """
    Commits local modifications in the workspace to a new branch, and pushes it up to GitHub.
    This safely bypasses mutating the human developer's local code.
    """
    try:
        subprocess.run(["git", "checkout", "-B", branch_name], cwd=workspace_path, check=True, capture_output=True)
        
        # Stage all real changes (including lios_* telemetry assets as requested)
        subprocess.run(["git", "add", "-A"], cwd=workspace_path, check=True, capture_output=True)
        
        # Check what's actually staged
        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=workspace_path, capture_output=True, text=True)
        staged_files = [f for f in staged.stdout.strip().split("\n") if f]
        
        if not staged_files:
            # Reset everything so we don't leave a dirty state
            subprocess.run(["git", "checkout", "--", "."], cwd=workspace_path, capture_output=True)
            return "SKIPPED: No files were fundamentally changed by the Agent. Working tree is completely clean."
        
        # Extract full textual diff for self-documenting commit message
        full_diff = subprocess.run(["git", "diff", "--cached"], cwd=workspace_path, capture_output=True, text=True).stdout
        
        try:
            from agent.llm_factory import get_llm
            from langchain_core.messages import HumanMessage
            
            llm = get_llm(role="planning")
            # Limit diff size aggressively to avoid exploding the context window
            capped_diff = full_diff[:15000]
            
            prompt = f"""Generate a concise, self-documenting Git commit message for the following codebase changes. 
Use exactly the Conventional Commits format (e.g. 'feat: description' or 'fix: description').
Do not wrap the response in markdown or backticks. Return nothing but the raw commit message text.

Diff:
{capped_diff}"""
            
            generated_msg = llm.invoke([HumanMessage(content=prompt)]).content.strip()
            
            # Sanitize any accidental wrapper artifacts from LLM
            generated_msg = generated_msg.strip('`').replace("markdown", "").strip()
            
            if generated_msg and len(generated_msg) > 5:
                commit_message = f"{generated_msg}\n\n[Lios-Agent Generated for {commit_message}]"
        except Exception as e:
            # Fallback to the generic task ID message if LLM fails
            print(f"⚠️ Failed to dynamically generate commit message: {e}")
            
        subprocess.run(["git", "commit", "-m", commit_message], cwd=workspace_path, check=True, capture_output=True)
        
        # Authenticate the Remote if a token is available
        if installation_id and repo_full_name:
            app_id = os.environ.get("GITHUB_APP_ID")
            pem_path = os.environ.get("GITHUB_PRIVATE_KEY_PATH", "./lios-agent.private-key.pem")
            if app_id and os.path.exists(pem_path):
                from github import GithubIntegration
                with open(pem_path, 'r') as pem_file:
                    private_key = pem_file.read()
                integration = GithubIntegration(app_id, private_key)
                access_token = integration.get_access_token(int(installation_id)).token
                # Set the remote URL to use the x-access-token
                auth_url = f"https://x-access-token:{access_token}@github.com/{repo_full_name}.git"
                subprocess.run(["git", "remote", "set-url", "origin", auth_url], cwd=workspace_path, check=True, capture_output=True)
                
        # Push the branch to the remote origin
        push_result = subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=workspace_path, check=True, capture_output=True, text=True)
        return f"SUCCESS: Successfully pushed branch `{branch_name}` to remote.\n\nOutput: {push_result.stdout}"
    except subprocess.CalledProcessError as e:
        return f"ERROR: Error during git operations: {e.stderr}"

def post_github_comment(repo_full_name: str, issue_number: int, installation_id: str, message: str) -> str:
    """Posts a comment on a GitHub issue using the GitHub App's credentials."""
    app_id = os.environ.get("GITHUB_APP_ID")
    pem_path = os.environ.get("GITHUB_PRIVATE_KEY_PATH", "./lios-agent.private-key.pem")
    
    if not app_id or not os.path.exists(pem_path):
        return "Error: GitHub App ID or PEM file missing."
        
    try:
        from github import GithubIntegration, Github
        with open(pem_path, 'r') as pem_file:
            private_key = pem_file.read()
            
        integration = GithubIntegration(app_id, private_key)
        access_token = integration.get_access_token(int(installation_id)).token
        
        gh = Github(access_token)
        repo = gh.get_repo(repo_full_name)
        issue = repo.get_issue(int(issue_number))
        issue = gh.get_repo(repo_full_name).get_issue(int(issue_number))
        issue.create_comment(message)
        return "Comment posted successfully."
    except Exception as e:
        return f"Error posting GitHub comment: {str(e)}"

def capture_simulator_screenshot(workspace_path: str, task_id: str) -> dict:
    """
    Boots the iOS Simulator, builds and launches the app, then captures a screenshot.
    Returns the absolute path to the screenshot PNG file.
    """
    import time
    timestamp = int(time.time())
    file_name = f"lios_screenshot_{timestamp}.png"
    screenshot_path = os.path.join(workspace_path, file_name)
    
    try:
        # 1. Find an available simulator device
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "available", "-j"],
            capture_output=True, text=True
        )
        import json
        devices = json.loads(result.stdout)
        
        # Find the first booted device, or boot one
        target_udid = None
        for runtime, device_list in devices.get("devices", {}).items():
            if "iOS" in runtime:
                for device in device_list:
                    if device.get("state") == "Booted":
                        target_udid = device["udid"]
                        break
                    elif not target_udid and device.get("isAvailable"):
                        target_udid = device["udid"]
                if target_udid:
                    break
        
        if not target_udid:
            return {"error": "Error: No available iOS simulator device found."}
        
        # 2. Boot if not already booted, and deeply wait for the iOS springboard daemon to complete launch
        subprocess.run(["open", "-a", "Simulator", "--args", "-CurrentDeviceUDID", target_udid], check=False)
        subprocess.run(["xcrun", "simctl", "bootstatus", target_udid, "-b"], check=False, capture_output=True)
        
        # 3. Find the correct directory dynamically by looking for .xcodeproj or .xcworkspace
        import glob
        build_dir = workspace_path
        
        candidates = []
        candidates.extend(glob.glob(os.path.join(workspace_path, "*.xcworkspace")))
        candidates.extend(glob.glob(os.path.join(workspace_path, "*/*.xcworkspace")))
        candidates.extend(glob.glob(os.path.join(workspace_path, "*.xcodeproj")))
        candidates.extend(glob.glob(os.path.join(workspace_path, "*/*.xcodeproj")))
        
        if candidates:
            # Prefer projects that look like apps (Demo, Example, App) for visual Simulator checks over pure frameworks
            app_projs = [p for p in candidates if any(x in p for x in ["Demo", "Example", "App"])]
            chosen_proj = app_projs[0] if app_projs else candidates[0]
            build_dir = os.path.dirname(chosen_proj)
            
        # Determine the correct scheme dynamically
        try:
            list_res = subprocess.run(["xcodebuild", "-list"], cwd=build_dir, capture_output=True, text=True)
            schemes = []
            in_schemes = False
            for line in list_res.stdout.split('\n'):
                if "Schemes:" in line:
                    in_schemes = True
                    continue
                if in_schemes and line.strip():
                    schemes.append(line.strip())
            app_schemes = [s for s in schemes if not s.endswith('Tests') and not s.endswith('Testing') and not "Preview" in s and "Demo" in s]
            if not app_schemes:
                app_schemes = [s for s in schemes if not s.endswith('Tests') and not s.endswith('Testing') and not "Preview" in s]
            active_scheme = app_schemes[0] if app_schemes else scheme
        except Exception:
            active_scheme = scheme
            
        # 4. Build for simulator
        subprocess.run(
            ["xcodebuild", "build", "-scheme", active_scheme,
             "-destination", f"platform=iOS Simulator,id={target_udid}",
             "-derivedDataPath", os.path.join(build_dir, "DerivedData")],
            cwd=build_dir, check=True, capture_output=True, text=True
        )
        
        # 5. Extract the compiled .app bundle and its Bundle ID to install & launch it natively
        app_paths = glob.glob(os.path.join(build_dir, "DerivedData/Build/Products/*-iphonesimulator/*.app"))
        if not app_paths:
            return {"error": "Error: Could not locate compiled .app bundle in DerivedData."}
        
        app_path = app_paths[0]
        subprocess.run(["xcrun", "simctl", "install", target_udid, app_path], check=True, capture_output=True)
        
        # Determine Bundle ID dynamically using PlistBuddy
        plist_path = os.path.join(app_path, "Info.plist")
        bundle_id_res = subprocess.run(["/usr/libexec/PlistBuddy", "-c", "Print CFBundleIdentifier", plist_path], capture_output=True, text=True)
        bundle_id = bundle_id_res.stdout.strip()
        
        if bundle_id:
            subprocess.run(["xcrun", "simctl", "launch", target_udid, bundle_id], check=False, capture_output=True)
        
        # 6. Wait for initial app launch to settle before taking baseline screenshot
        import time
        time.sleep(6)
        
        # 7. Capture initial baseline screenshot
        subprocess.run(
            ["xcrun", "simctl", "io", target_udid, "screenshot", screenshot_path],
            check=True, capture_output=True
        )
        
        # Use native macOS SIPS to permanently downscale the Retina image to 800px
        subprocess.run(["sips", "-Z", "800", screenshot_path], check=False, capture_output=True)
        
        return {
            "screenshot_path": screenshot_path,
            "device_udid": target_udid,
            "bundle_id": bundle_id or ""
        }
    except subprocess.CalledProcessError as e:
        return {"error": f"Simulator capture failed: {e.stderr if e.stderr else str(e)}"}
    except Exception as e:
        return {"error": f"Simulator capture error: {str(e)}"}

def get_maestro_bin() -> str:
    """Resolve the Maestro CLI binary path."""
    home_bin = os.path.expanduser("~/.maestro/bin/maestro")
    if os.path.exists(home_bin):
        return home_bin
    return "maestro"

def get_maestro_hierarchy(device_udid: str) -> str:
    """
    Dumps the live iOS accessibility hierarchy from the running simulator.
    Uses Maestro's compact CSV format for concise LLM consumption.
    Returns the raw hierarchy text, or an empty string on failure.
    """
    maestro_bin = get_maestro_bin()
    try:
        result = subprocess.run(
            [maestro_bin, "--device", device_udid, "hierarchy", "--compact"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception as e:
        print(f"⚠️ Maestro hierarchy dump failed: {e}")
        return ""

def _maestro_selector_for_label(label: str) -> str:
    """
    Determine whether to use Maestro's `id:` or `text:` selector.
    
    Per Maestro docs:
    - `id:` maps to iOS accessibilityIdentifier (gold standard, most reliable)
    - `text:` maps to iOS accessibilityLabel / visible text
    
    We use `id:` when the label looks like a programmatic identifier 
    (snake_case, kebab-case, no spaces), and `text:` for human-readable labels.
    """
    import re
    # If it looks like a programmatic ID (contains underscores/hyphens, no spaces)
    if re.match(r'^[a-zA-Z0-9_.-]+$', label) and ('_' in label or '-' in label or '.' in label):
        return f'id: "{label}"'
    return f'text: "{label}"'

def run_maestro_single_tap(device_udid: str, workspace_path: str, bundle_id: str, label: str) -> bool:
    """
    Executes a robust Maestro tap: uses retryTapIfNoChange so early taps on 
    not-yet-ready UI elements are automatically retried, and waits for settle.
    Automatically uses `id:` selector for programmatic identifiers and `text:` for labels.
    """
    selector = _maestro_selector_for_label(label)
    flow_content = f"""appId: {bundle_id}
---
- tapOn:
    {selector}
    retryTapIfNoChange: true
    waitToSettleTimeoutMs: 3000
- waitForAnimationToEnd
"""
    flow_path = os.path.join(workspace_path, "maestro_step.yaml")
    with open(flow_path, "w") as f:
        f.write(flow_content)
    
    maestro_bin = get_maestro_bin()
    result = subprocess.run(
        [maestro_bin, "--device", device_udid, "test", flow_path],
        check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"    📋 Maestro stderr: {result.stderr[-300:]}" if result.stderr else "    📋 Maestro: no stderr")
    return result.returncode == 0

def run_maestro_scroll(device_udid: str, workspace_path: str, bundle_id: str, 
                       direction: str = "DOWN", target_label: str = None) -> bool:
    """
    Executes a Maestro scroll. If target_label is provided, uses scrollUntilVisible
    which is much more reliable than blind scrolling. Falls back to plain scroll.
    """
    if target_label:
        # scrollUntilVisible: scroll until element with target text appears
        flow_content = f"""appId: {bundle_id}
---
- scrollUntilVisible:
    element: "{target_label}"
    direction: {direction.upper()}
    timeout: 15000
    centerElement: true
"""
    elif direction.upper() == "DOWN":
        flow_content = f"""appId: {bundle_id}
---
- scroll
- waitForAnimationToEnd
"""
    else:
        flow_content = f"""appId: {bundle_id}
---
- swipe:
    direction: {direction.upper()}
    duration: 400
- waitForAnimationToEnd
"""
    
    flow_path = os.path.join(workspace_path, "maestro_step.yaml")
    with open(flow_path, "w") as f:
        f.write(flow_content)
    
    maestro_bin = get_maestro_bin()
    result = subprocess.run(
        [maestro_bin, "--device", device_udid, "test", flow_path],
        check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"    📋 Maestro stderr: {result.stderr[-300:]}" if result.stderr else "    📋 Maestro: no stderr")
    return result.returncode == 0

def synthesize_replayable_flow(workspace_path: str, bundle_id: str, action_history: list) -> str:
    """
    After the navigation loop completes, synthesize a complete multi-step Maestro YAML 
    from the action history. This flow can be replayed independently for regression testing
    and is stored alongside the PR.
    
    Returns the path to the synthesized flow file.
    """
    lines = [
        f"appId: {bundle_id}",
        "---",
        "- launchApp",
        "- startRecording: lios_navigation",
        "- waitForAnimationToEnd",
        ""
    ]
    
    for action in action_history:
        if action.startswith("TAP:"):
            label = action.replace("TAP:", "").strip().strip('"').strip("'")
            selector = _maestro_selector_for_label(label)
            lines.append(f'- tapOn:')
            lines.append(f'    {selector}')
            lines.append(f'    retryTapIfNoChange: true')
            lines.append(f'    waitToSettleTimeoutMs: 3000')
            lines.append(f'- waitForAnimationToEnd')
            lines.append("")
        elif action.startswith("SCROLL:"):
            direction = action.replace("SCROLL:", "").strip().upper()
            lines.append(f'- scroll')
            lines.append(f'- waitForAnimationToEnd')
            lines.append("")
    
    lines.append("- takeScreenshot: lios_final_state")
    lines.append("- stopRecording")
    lines.append("")
    
    flow_path = os.path.join(workspace_path, "maestro_flow.yaml")
    with open(flow_path, "w") as f:
        f.write("\n".join(lines))
    
    print(f"  📄 Synthesized replayable Maestro flow: {flow_path}")
    return flow_path

def navigate_to_target_view(device_udid: str, workspace_path: str, bundle_id: str, instructions: str, blueprint: dict) -> list:
    """
    Two-phase intelligent navigation:
    Phase 1: Analyze the source code structure to deduce the navigation path.
    Phase 2: Use the Vision LLM on screenshots + hierarchy to execute navigation.
    
    Returns a list of navigation log entries.
    """
    from agent.llm_factory import get_llm
    import time
    import base64
    
    nav_log = []
    max_steps = 7
    action_history = []  # Track every action taken to prevent loops
    
    # Gather context about what changed
    files = blueprint.get("files_to_modify", []) + blueprint.get("files_to_create", [])
    components = blueprint.get("architecture_components", [])
    file_paths = [str(f.get("filepath", "")) for f in files]
    file_list = ", ".join(file_paths)
    
    print(f"  📍 Target files: {file_list}")
    print(f"  🏗️ Components: {', '.join(components)}")
    
    # ─── Phase 1: Source Code Intelligence ───
    nav_hints = _analyze_navigation_from_source(workspace_path, file_paths)
    print(f"  🧭 Source code nav hints: {nav_hints}")
    
    # ─── Phase 2: Vision-Guided Navigation Loop ───
    for step in range(max_steps):
        # 1. Take a live screenshot of current screen state
        step_screenshot = os.path.join(workspace_path, f"maestro_nav_step_{step}.png")
        subprocess.run(
            ["xcrun", "simctl", "io", device_udid, "screenshot", step_screenshot],
            check=False, capture_output=True
        )
        subprocess.run(["sips", "-Z", "600", step_screenshot], check=False, capture_output=True)
        
        # 2. Get hierarchy for element labels
        hierarchy = get_maestro_hierarchy(device_udid)
        meaningful_lines = []
        if hierarchy:
            for line in hierarchy.split("\n"):
                if "accessibilityText=" in line or "text=" in line or "resource-id=" in line:
                    meaningful_lines.append(line)
        
        labeled_elements = "\n".join(meaningful_lines) if meaningful_lines else "No labeled elements found."
        print(f"  🔍 Step {step+1}: {len(meaningful_lines)} labeled elements on screen")
        
        # 3. Build action history context for the LLM
        history_context = ""
        if action_history:
            history_context = "\n\nACTIONS ALREADY TAKEN (do NOT repeat these):\n"
            for i, action in enumerate(action_history):
                history_context += f"  Step {i+1}: {action}\n"
            history_context += "If you already tapped an element and the screen hasn't changed to the target, the element is probably a tab you're already on. Try a DIFFERENT element or respond DONE.\n"
        
        # 4. Encode the screenshot for the Vision LLM
        try:
            vision_llm = get_llm(role="vision")
            
            with open(step_screenshot, "rb") as img_file:
                image_b64 = base64.b64encode(img_file.read()).decode("utf-8")
            
            from langchain_core.messages import HumanMessage
            message = HumanMessage(content=[
                {"type": "text", "text": f"""You are navigating an iOS app to reach a specific screen.

TASK: "{instructions}"
FILES CHANGED: {file_list}
NAVIGATION HINTS FROM SOURCE CODE: {nav_hints}

LABELED ELEMENTS ON SCREEN:
{labeled_elements}
{history_context}
You have 3 possible actions:

1. DONE — The target screen is already visible, or the modified view is on this screen.
2. TAP: <label> — Tap on a visible element to navigate deeper. Use ONLY text you can see in the screenshot or labeled elements.
3. SCROLL: DOWN (or UP) — The target view might be off-screen in a scrollable area.

Decision guide:
- If the changes affect the root/home screen, respond: DONE
- If you see the target view content, respond: DONE
- If you already tapped something and the screen looks the same, respond: DONE (you're already there)
- If the screen is scrollable and the target might be off-screen, respond: SCROLL: DOWN
- If there's a walkthrough/onboarding blocking, try: TAP: <dismiss button>
- Otherwise navigate with: TAP: <label>

Respond with ONLY "DONE", "TAP: <label>", or "SCROLL: DOWN/UP" — nothing else."""},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
            ])
            
            response = vision_llm.invoke([message]).content.strip()
            print(f"  🧠 Vision LLM decided: {response}")
            
        except Exception as e:
            print(f"  ⚠️ Vision LLM failed ({e}), falling back to text-only...")
            try:
                text_llm = get_llm(role="planning")
                fallback_prompt = f"""You are navigating an iOS app. The developer modified: {file_list}
Navigation hints: {nav_hints}
Labeled elements on screen: {labeled_elements}
{history_context}
Actions: DONE (target visible), TAP: <label>, SCROLL: DOWN/UP (if target is off-screen).
If the target is already showing, changes are on the home screen, or you already tapped the same element, respond DONE.
Respond with ONLY "DONE", "TAP: <label>", or "SCROLL: DOWN/UP"."""
                response = text_llm.invoke(fallback_prompt).content.strip()
                print(f"  🧠 Fallback LLM decided: {response}")
            except Exception as e2:
                nav_log.append(f"Step {step+1}: Both LLMs failed: {e2}")
                print(f"  ❌ Both LLMs failed: {e2}")
                break
        
        # ─── Loop Detection ───
        normalized_response = response.strip()
        if normalized_response in action_history:
            nav_log.append(f"Step {step+1}: Loop detected ('{normalized_response}' was already attempted). Stopping.")
            print(f"  🔄 Loop detected! Already did '{normalized_response}'. Stopping navigation.")
            break
        
        if response.startswith("DONE"):
            nav_log.append(f"Step {step+1}: Target screen reached.")
            print(f"  ✅ Target screen reached.")
            break
        elif response.startswith("TAP:"):
            label = response.replace("TAP:", "").strip().strip('"').strip("'")
            action_history.append(normalized_response)
            nav_log.append(f"Step {step+1}: Tapping '{label}'")
            print(f"  🎯 Step {step+1}: Tapping '{label}'")
            
            success = run_maestro_single_tap(device_udid, workspace_path, bundle_id, label)
            if success:
                print(f"  ✅ Maestro tap executed successfully")
            else:
                nav_log.append(f"  ↳ Maestro tap failed!")
                print(f"  ❌ Maestro tap on '{label}' failed! Stopping.")
                break
            
            time.sleep(3)
        elif response.startswith("SCROLL:"):
            direction = response.replace("SCROLL:", "").strip().upper()
            if direction not in ("DOWN", "UP", "LEFT", "RIGHT"):
                direction = "DOWN"
            action_history.append(normalized_response)
            nav_log.append(f"Step {step+1}: Scrolling {direction}")
            print(f"  📜 Step {step+1}: Scrolling {direction}")
            
            success = run_maestro_scroll(device_udid, workspace_path, bundle_id, direction)
            if success:
                print(f"  ✅ Maestro scroll executed successfully")
            else:
                nav_log.append(f"  ↳ Scroll failed!")
                print(f"  ❌ Scroll {direction} failed!")
                break
            
            time.sleep(2)
        else:
            nav_log.append(f"Step {step+1}: Unexpected: {response}")
            print(f"  ⚠️ Unexpected: {response}")
            break
    
    # Cleanup step screenshots
    import glob
    for f in glob.glob(os.path.join(workspace_path, "maestro_nav_step_*.png")):
        os.remove(f)
    
    # Synthesize a complete, replayable Maestro YAML from the action history
    if action_history:
        synthesize_replayable_flow(workspace_path, bundle_id, action_history)
    else:
        # No actions taken — write a simple navigation log
        flow_path = os.path.join(workspace_path, "maestro_flow.yaml")
        with open(flow_path, "w") as f:
            f.write(f"# Maestro navigation: no actions needed (target was already visible)\n")
    
    return nav_log

def _analyze_navigation_from_source(workspace_path: str, file_paths: list) -> str:
    """
    Phase 1: Use the Planning LLM to analyze the modified file paths AND their content 
    to deduce navigation hints. This is framework-agnostic and adapts to custom 
    declarative UI frameworks (like Construkt).
    """
    from agent.llm_factory import get_llm
    
    file_contents = ""
    
    # 1. Gather modified file contents
    for fp in file_paths:
        if not fp.endswith(".swift"):
            continue
        
        full_path = fp if os.path.isabs(fp) else os.path.join(workspace_path, fp)
        try:
            if os.path.exists(full_path):
                with open(full_path, "r", errors="ignore") as f:
                    content = f.read()
                    # Truncate long files to keep prompt manageable
                    if len(content) > 3000:
                        content = content[:1500] + "\n...[truncated]...\n" + content[-1500:]
                    file_contents += f"\n--- {fp} ---\n{content}\n"
        except Exception:
            pass
    
    # 2. Gather navigation graph structure (Coordinators/Routers)
    try:
        import glob
        nav_files = []
        for pattern in ["*Coordinator*.swift", "*Router*.swift", "*TabBar*.swift"]:
            nav_files += glob.glob(os.path.join(workspace_path, "**", pattern), recursive=True)
        
        for nf in nav_files[:2]:  # Limit to 2 to avoid blowing up context
            try:
                with open(nf, "r", errors="ignore") as f:
                    content = f.read()
                    if len(content) > 2000:
                        content = content[:2000] + "\n...[truncated]"
                    file_contents += f"\n--- {os.path.basename(nf)} (Navigation Graph) ---\n{content}\n"
            except Exception:
                pass
    except Exception:
        pass

    if not file_contents:
        return "No clear navigation hints from source code."

    prompt = f"""You are an expert iOS tester using the Maestro framework.
The developer has modified the following Swift files. Analyze them to provide navigation hints for a test agent.

CRITICAL INSTRUCTION: Do not make any assumptions about the UI framework or syntax being used. The project may use a custom, internal declarative framework. Adapt your analysis purely based on the structure and semantics found in the provided code.

Provide a highly concise summary (2-3 sentences) focusing on:
1. Location: What screen or feature is this?
2. Scrolling: Based purely on the code provided, are the modified elements placed inside a scrolling or list-type container? Must the agent scroll to reach the modified UI?
3. Targets: Are there any specific accessibilityIdentifiers, labels, or programmatic IDs the agent should target to reach this view?

File contents:
{file_contents}

Return ONLY the concatenated text of your hints. No conversational filler."""

    try:
        llm = get_llm(role="planning")
        response = llm.invoke(prompt).content.strip()
        return response
    except Exception as e:
        print(f"  ⚠️ Intelligent source analysis failed: {e}")
        # Fallback to basic path heuristics
        hints = [f"Modified: {os.path.basename(p)}" for p in file_paths]
        return "Source analysis failed. Files: " + ", ".join(hints)

def validate_ui_with_vision(screenshot_path: str, design_constraints: str) -> dict:
    """
    Sends a simulator screenshot to a Vision-capable LLM alongside design constraints
    (e.g., Figma tokens, color palette rules) for automated UI/UX compliance checking.
    
    Returns a dict with 'passed' (bool) and 'feedback' (str).
    """
    if not os.path.exists(screenshot_path):
        return {"passed": False, "feedback": f"Screenshot not found at {screenshot_path}"}
    
    try:
        import base64
        from agent.llm_factory import get_llm
        from langchain_core.messages import HumanMessage
        
        # Encode screenshot as base64 for multimodal input
        with open(screenshot_path, "rb") as img_file:
            image_data = base64.b64encode(img_file.read()).decode("utf-8")
        
        llm = get_llm(role="vision")  # Vision-capable model needed
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": f"""You are a Senior iOS UI/UX reviewer.
                
Analyze this simulator screenshot against the following design constraints:
{design_constraints}

Evaluate:
1. Color palette compliance (are the correct design tokens used?)
2. Layout structure (spacing, alignment, hierarchy)
3. Typography consistency
4. Component completeness (are all required UI elements present?)

Respond with EXACTLY one of:
- "PASS: <brief confirmation>" if the UI meets all constraints
- "FAIL: <specific issues found>" if there are violations"""},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
            ]
        )
        
        response = llm.invoke([message])
        content = response.content.strip()
        
        if content.startswith("FAIL:"):
            return {"passed": False, "feedback": content.replace("FAIL:", "").strip()}
        else:
            return {"passed": True, "feedback": content.replace("PASS:", "").strip()}
            
    except Exception as e:
        return {"passed": False, "feedback": f"Vision LLM call failed: {str(e)}"}

@tool
def fetch_external_link(url: str) -> str:
    """
    Fetches raw text content from external web links or code snippets.
    Useful for reading external reference repositories, gists, or GitHub pages mentioned in an issue.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # If it's a GitHub URL, suggest appending ?raw=true for code
        if "github.com" in url and "blob" in url and "?raw=true" not in url:
            return f"Tip: For GitHub file links, try fetching the raw content URL instead (e.g., change /blob/ to /raw/). Here is the HTML: {response.text[:500]}..."
            
        text = response.text
        # Truncate to avoid exploding the context window (limit to ~10,000 characters)
        if len(text) > 10000:
            return text[:10000] + "\n...[Content truncated due to length constraint]..."
            
        return text
    except Exception as e:
        return f"Failed to fetch external link {url}: {str(e)}"
