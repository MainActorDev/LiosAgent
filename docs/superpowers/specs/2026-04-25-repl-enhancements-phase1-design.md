# REPL Enhancements Phase 1 Design

**Topic**: Command History and Live Syntax Highlighting for the Universal REPL.

## Overview
Phase 1 of enhancing the `UniversalREPL` will introduce persistent command history and live syntax highlighting. This keeps the implementation iterative and self-contained within `agent/repl.py`. Phase 2 (File Auto-completion) will be tackled separately in the future.

## Architecture & Components

**1. Persistent Command History**
- **Library**: `prompt_toolkit.history.FileHistory`.
- **Implementation**: The `PromptSession` in `start_interactive_session` will be initialized with `history=FileHistory(history_file_path)`.
- **Storage**: The history file will be stored at `~/.config/lios/.lios_history`. We must ensure the `~/.config/lios` directory exists before initializing `FileHistory`.

**2. Live Syntax Highlighting**
- **Library**: `prompt_toolkit.lexers.PygmentsLexer` and custom `pygments.lexer.RegexLexer`.
- **Implementation**: We will create a `LiosLexer` class inside `agent/repl.py` that inherits from `RegexLexer`.
- **Color Scheme & Tokens**:
  - Slash commands (`^/\w+`): Highlighted in **cyan** (mapped to `Token.Keyword`).
  - File references (`@[\w./-]+`): Highlighted in **green** (mapped to `Token.Name.Class` or similar).
  - Standard text: Default terminal color.
- **Integration**: The `PromptSession` will be configured with `lexer=PygmentsLexer(LiosLexer)` and an appropriate `style` dictionary mapping Pygments tokens to prompt_toolkit styles.

## Constraints & Error Handling
- The `prompt_toolkit` library is already present in `requirements.txt`.
- `pygments` needs to be added to `requirements.txt` if not already present.
- If the `~/.config/lios` directory cannot be created (e.g., permission issues), the REPL should gracefully fall back to an `InMemoryHistory` or handle the exception so the CLI does not crash.

## Testing Strategy
- The syntax highlighting is primarily a visual feature, to be tested manually by typing slash commands and `@` paths in the REPL.
- Persistent history can be tested by exiting the REPL and starting it again, verifying that the Up arrow restores previous inputs.