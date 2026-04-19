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
    seed_path = os.path.join(BASE_WORKSPACE_DIR, "seed_cache")
    workspace_path = os.path.join(BASE_WORKSPACE_DIR, task_id)
    
    try:
        # 1. Maintain the Seed Cache
        if not os.path.exists(seed_path):
            subprocess.run(["git", "clone", repo_url, seed_path], check=True, capture_output=True)
        else:
            subprocess.run(["git", "reset", "--hard"], cwd=seed_path, check=True, capture_output=True)
            subprocess.run(["git", "checkout", "main"], cwd=seed_path, check=True, capture_output=True)
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
        
        return f"Hot Workspace cloned via APFS at: {workspace_path}"
    except subprocess.CalledProcessError as e:
        return f"Error during workspace prep: {e.stderr}"

@tool
def read_workspace_file(workspace_path: str, file_relative_path: str) -> str:
    """Read the contents of a specific file inside the isolated workspace."""
    full_path = os.path.join(workspace_path, file_relative_path)
    if not os.path.exists(full_path):
        return f"Error: File '{file_relative_path}' not found in workspace."
        
    try:
        with open(full_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
def write_workspace_file(workspace_path: str, file_relative_path: str, content: str) -> str:
    """
    Overwrites or creates a file inside the isolated workspace with the provided content.
    Use this ONLY for creating brand new files. For modifying existing files, use patch_workspace_file instead.
    """
    full_path = os.path.join(workspace_path, file_relative_path)
    
    # Ensure directory exists (e.g. if creating a new Feature module)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
    try:
        with open(full_path, "w") as f:
            f.write(content)
        return f"Successfully wrote to: {file_relative_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

@tool
def read_workspace_file_lines(workspace_path: str, file_relative_path: str, start_line: int = 1, end_line: int = 50) -> str:
    """
    Read a specific range of lines from a file, with line numbers prepended.
    This is the preferred way to explore large files before patching.
    Use this instead of read_workspace_file when the file might be large (>100 lines).
    """
    full_path = os.path.join(workspace_path, file_relative_path)
    if not os.path.exists(full_path):
        return f"Error: File '{file_relative_path}' not found in workspace."
        
    try:
        with open(full_path, "r") as f:
            all_lines = f.readlines()
        
        total = len(all_lines)
        start_line = max(1, start_line)
        end_line = min(total, end_line)
        
        numbered = []
        for i in range(start_line - 1, end_line):
            numbered.append(f"{i + 1}: {all_lines[i].rstrip()}")
        
        header = f"[{file_relative_path}] Lines {start_line}-{end_line} of {total} total"
        return header + "\n" + "\n".join(numbered)
    except Exception as e:
        return f"Error reading file lines: {str(e)}"

@tool
def patch_workspace_file(workspace_path: str, file_relative_path: str, start_line: int, end_line: int, new_content: str) -> str:
    """
    Surgically replace lines start_line through end_line (inclusive, 1-indexed) with new_content.
    This is the PREFERRED tool for modifying existing files. It prevents hallucination
    by only touching the exact lines that need to change, leaving the rest of the file untouched.
    
    Steps: 
    1. First use read_workspace_file_lines to see the target area with line numbers.
    2. Then call this tool with the exact start_line and end_line to replace.
    """
    full_path = os.path.join(workspace_path, file_relative_path)
    if not os.path.exists(full_path):
        return f"Error: File '{file_relative_path}' not found."
        
    try:
        with open(full_path, "r") as f:
            lines = f.readlines()
        
        total = len(lines)
        if start_line < 1 or end_line > total or start_line > end_line:
            return f"Error: Invalid line range {start_line}-{end_line}. File has {total} lines."
        
        # Ensure new_content ends with newline for clean splicing
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
        
        # Splice: keep lines before start, inject new content, keep lines after end
        new_lines = lines[:start_line - 1] + [new_content] + lines[end_line:]
        
        with open(full_path, "w") as f:
            f.writelines(new_lines)
        
        new_total = len(new_lines)
        return f"Patched {file_relative_path}: replaced lines {start_line}-{end_line} ({end_line - start_line + 1} lines removed, new content injected). File now has {new_total} lines."
    except Exception as e:
        return f"Error patching file: {str(e)}"

def prepare_project_structure(workspace_path: str):
    if os.path.exists(os.path.join(workspace_path, "project.yml")):
        subprocess.run(["rtk", "xcodegen", "generate"], cwd=workspace_path, check=False)
    elif os.path.exists(os.path.join(workspace_path, "Tuist", "Project.swift")):
        subprocess.run(["rtk", "tuist", "generate"], cwd=workspace_path, check=False)
    elif os.path.exists(os.path.join(workspace_path, "Package.swift")):
        subprocess.run(["rtk", "swift", "package", "resolve"], cwd=workspace_path, check=False)

def execute_xcodebuild(workspace_path: str) -> str:
    """
    Dynamically generates the project if needed, then attempts to compile it,
    piping output through rtk to save LLM tokens.
    """
    if not shutil.which("rtk"):
        return "FATAL ERROR: The `rtk` (Rust Token Kit) CLI proxy is missing from the system PATH. Execution halted to prevent API token exhaustion."

    prepare_project_structure(workspace_path)
    
    # Fallback to pure xcodebuild if no custom fast-build script exists
    build_cmd = ["rtk", "xcodebuild", "build", "-scheme", "App", "-destination", "generic/platform=iOS Simulator"]
    
    if os.path.exists(os.path.join(workspace_path, "scripts", "xcodebuild_cached.sh")):
        build_cmd = ["rtk", "bash", "./scripts/xcodebuild_cached.sh"]
        
    try:
        # We use cwd=workspace_path so xcodebuild runs in the correct directory context
        result = subprocess.run(
            build_cmd,
            cwd=workspace_path,
            capture_output=True,
            text=True
        )
        
        # RTK heavily compresses logs, so we can return them safely in full
        if result.returncode == 0:
            return f"Build SUCCESS!\n\nRTK Distilled Output:\n{result.stdout}"
        else:
            return f"Build FAILED!\n\nRTK Distilled Error Log:\n{result.stderr}\n\nStdout:\n{result.stdout}"
            
    except Exception as e:
        return f"Failed to execute build script: {str(e)}"

def commit_and_push_branch(workspace_path: str, branch_name: str, commit_message: str) -> str:
    """
    Commits local modifications in the workspace to a new branch, and pushes it up to GitHub.
    This safely bypasses mutating the human developer's local code.
    """
    try:
        subprocess.run(["git", "checkout", "-B", branch_name], cwd=workspace_path, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=workspace_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", commit_message], cwd=workspace_path, check=True, capture_output=True)
        # Push the branch to the remote origin
        push_result = subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=workspace_path, check=True, capture_output=True, text=True)
        return f"Successfully pushed branch `{branch_name}` to remote. Output: {push_result.stdout}"
    except subprocess.CalledProcessError as e:
        return f"Error during git push: {e.stderr}"

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
    screenshot_path = os.path.join(workspace_path, ".lios_screenshot.png")
    
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
        
        llm = get_llm(role="planning")  # Vision-capable model needed
        
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
        
        result = llm.invoke([message])
        response = result.content.strip()
        
        passed = response.upper().startswith("PASS")
        return {"passed": passed, "feedback": response}
    except Exception as e:
        return {"passed": False, "feedback": f"Vision validation error: {str(e)}"}

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
