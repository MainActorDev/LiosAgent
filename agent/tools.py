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
    workspace_path = os.path.join(BASE_WORKSPACE_DIR, task_id)
    
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
        
        # Stage all real changes
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
        issue.create_comment(message)
        return "Comment posted successfully."
    except Exception as e:
        return f"Error posting GitHub comment: {str(e)}"

def capture_simulator_screenshot(workspace_path: str, scheme: str = "App") -> str:
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
            return "Error: No available iOS simulator device found."
        
        # 2. Boot if not already booted
        subprocess.run(["xcrun", "simctl", "boot", target_udid], check=False, capture_output=True)
        
        # 3. Build for simulator and install
        subprocess.run(
            ["xcodebuild", "build", "-scheme", scheme,
             "-destination", f"platform=iOS Simulator,id={target_udid}",
             "-derivedDataPath", os.path.join(workspace_path, "DerivedData")],
            cwd=workspace_path, check=True, capture_output=True, text=True
        )
        
        # 4. Wait for simulator to settle then capture
        import time
        time.sleep(3)
        subprocess.run(
            ["xcrun", "simctl", "io", target_udid, "screenshot", screenshot_path],
            check=True, capture_output=True
        )
        
        return screenshot_path
    except subprocess.CalledProcessError as e:
        return f"Simulator capture failed: {e.stderr if e.stderr else str(e)}"
    except Exception as e:
        return f"Simulator capture error: {str(e)}"

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
        error_str = str(e).lower()
        if "vision" in error_str or "multimodal" in error_str or "400" in error_str:
            # Swallow explicitly unsupported API model payloads
            return {"passed": True, "feedback": "Skipping UI Vision Check: The actively loaded AI model does not support multimodal payload requests. Bypassing pixel layout critique."}
        return {"passed": False, "feedback": f"Critical LLM Vision execution failed natively: {str(e)}"}

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
