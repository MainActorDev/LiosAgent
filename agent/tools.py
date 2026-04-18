import os
import subprocess
import shutil
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
    The agent should use this to apply coding modifications.
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
