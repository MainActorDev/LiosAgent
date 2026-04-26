import os
import yaml
import json
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

# Resolves from the Current Working Directory where `lios` was executed
VAULTS_ROOT = os.path.abspath(os.path.join(os.getcwd(), ".lios", "epics"))

class VaultManager:
    """
    Manages the physical directories and state for Epics and Stories.
    Shifts from a single opaque database to transparent, git-trackable feature vaults.
    """
    
    @staticmethod
    def _ensure_dir(path: str):
        if not os.path.exists(path):
            os.makedirs(path)
            
    @classmethod
    def create_epic_vault(cls, epic_name: str) -> str:
        """Creates the root directory for an Epic."""
        path = os.path.join(VAULTS_ROOT, epic_name)
        cls._ensure_dir(path)
        cls._ensure_dir(os.path.join(path, "stories"))
        return path
        
    @classmethod
    def create_story_vault(cls, epic_name: str, story_id: str) -> str:
        """Creates a nested directory for a specific Story within an Epic."""
        path = os.path.join(VAULTS_ROOT, epic_name, "stories", story_id)
        cls._ensure_dir(path)
        return path
        
    @classmethod
    def get_checkpointer(cls, vault_path: str) -> SqliteSaver:
        """
        Returns a LangGraph SqliteSaver scoped entirely to this specific vault.
        This isolates state per-feature rather than a global opaque database.
        """
        cls._ensure_dir(vault_path)
        db_path = os.path.join(vault_path, ".state.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        checkpointer.setup()
        return checkpointer

    @classmethod
    def dump_human_readable_state(cls, vault_path: str, state_dict: dict):
        """
        Dumps the LangGraph state into a transparent, version-controllable YAML file.
        This provides the 'Human Fallback' capability.
        """
        yaml_path = os.path.join(vault_path, "state.yml")
        
        # Filter out massive binary/raw text fields that clutter the YAML
        clean_state = {k: v for k, v in state_dict.items() if k not in ["mcp_context", "agent_skills", "progress_log"]}
        
        with open(yaml_path, "w") as f:
            yaml.dump(clean_state, f, default_flow_style=False)
            
    @classmethod
    def save_blueprint(cls, vault_path: str, blueprint: dict):
        """Saves the Architectural Blueprint as a markdown file."""
        md_path = os.path.join(vault_path, "blueprint.md")
        with open(md_path, "w") as f:
            f.write(f"# Blueprint: {blueprint.get('feature_name', 'Unknown')}\n\n")
            f.write("## Files to Create\n")
            for item in blueprint.get("files_to_create", []):
                f.write(f"- `{item['filepath']}`: {item['purpose']}\n")
            f.write("\n## Files to Modify\n")
            for item in blueprint.get("files_to_modify", []):
                f.write(f"- `{item['filepath']}`: {item['purpose']}\n")
            f.write("\n## Architecture Components\n")
            for item in blueprint.get("architecture_components", []):
                f.write(f"- {item}\n")
