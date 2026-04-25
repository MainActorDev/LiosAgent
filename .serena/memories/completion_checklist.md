# Lios-Agent Completion Checklist

When finishing a task for the Lios-Agent codebase itself (not the target iOS app), ensure you:
1.  **Format/Lint**: Adhere to the Python conventions (though no explicit linter/formatter is defined in `requirements.txt`).
2.  **Test**: Manually run the modified CLI command (e.g. `./lios --help` or `./lios epic ...`) to verify functionality.
3.  **Documentation**: If modifying the `cli.py` or adding a new command, ensure the Typer docstrings are updated and `README.md` reflects the new feature.
4.  **Dependencies**: If adding a new dependency, ensure it is added to `requirements.txt` and is compatible with Python 3.10+ and the current LangGraph/LangChain stack.
5.  **State Management**: If modifying the vault or state, ensure `VaultManager` (`agent/vault_manager.py`) correctly handles the serialization and directory creation.
6.  **OS Compatibility**: Keep in mind that tools and system commands are heavily optimized for macOS (`darwin`).

If you are modifying the generated iOS code (via the agent):
1.  **Xcodebuild**: The `agent/tools.py` will run `execute_xcodebuild` to ensure the project compiles.
2.  **Maestro Validation**: The pipeline will capture a screenshot (`capture_simulator_screenshot`) and validate the UI using multimodality (`validate_ui_with_vision`) and `maestro`.
3.  **GitHub PR**: The agent will autonomously `commit_and_push_branch` and `post_github_comment`.