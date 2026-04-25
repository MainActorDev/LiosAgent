# REPL Enhancements Phase 2 Design

**Topic**: File Path Auto-completion for the Universal REPL.

## Overview
Phase 2 of enhancing the `UniversalREPL` introduces explicit file auto-completion when the user types `@`. This builds upon Phase 1 and integrates tightly with `prompt_toolkit`.

## Architecture & Components

**1. Custom Completer**
- **Library**: `prompt_toolkit.completion.Completer` and `prompt_toolkit.completion.Completion`.
- **Implementation**: We will create a `FileMentionCompleter` class inside `agent/repl.py`.
- **Integration**: The `PromptSession` in `UniversalREPL.start_interactive_session()` will be configured with `completer=FileMentionCompleter()`.

**2. Logic and Constraints**
- **Trigger**: Explicit trigger only. The logic activates when it parses a token prefixed with `@` right before the cursor.
- **Parsing**: The string following the `@` is treated as a path relative to the current working directory.
- **Directory Traversal**: The completer reads the resolved directory using standard library tools (`os.listdir` or `pathlib`).
- **Hidden Files Filter**: Any file or directory starting with a dot (`.`) is strictly ignored and excluded from suggestions.
- **Directory Restriction**: Navigation outside the current working directory using `../` will be blocked or ignored by normalizing the path and ensuring it resides within the project root.

## Error Handling & Robustness
- If the resolved directory does not exist, the completer will gracefully yield nothing without throwing exceptions that crash the REPL.
- Permission errors reading directories will be caught and ignored, yielding no suggestions for those paths.

## Testing Strategy
- Create unit tests in `tests/test_repl_completer.py`.
- Mock filesystem operations or use a `pytest.fixture` to create a controlled temporary directory structure containing regular files, hidden files, and subdirectories.
- Assert that typing `@` yields suggestions only for visible files in the root.
- Assert that typing `@subfolder/` yields visible files within `subfolder`.
- Assert that attempting to navigate out (e.g., `@../`) yields no results or is securely contained.

