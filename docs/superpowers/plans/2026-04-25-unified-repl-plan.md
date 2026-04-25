# Unified CLI REPL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an interactive REPL when typing `lios` without arguments, supporting Typer slash commands and conversational chat.

**Architecture:** We will modify Typer to use `invoke_without_command=True` in `cli.py` to trigger the default mode. `agent/repl.py` will host the new `start_interactive_session()` function powered by `prompt_toolkit`. It parses slash commands to invoke existing `cli.py` functions and routes natural text to a lightweight LangChain LLM conversation loop.

**Tech Stack:** Python, Typer, `prompt_toolkit`, LangChain, Rich

---

### Task 1: Refactor `cli.py` entry point

**Files:**
- Modify: `cli.py`

- [ ] **Step 1: Write the failing test**

```python
# Create tests/test_cli_default.py
from typer.testing import CliRunner
from cli import app

runner = CliRunner()

def test_default_invocation_calls_repl(mocker):
    # Mock the REPL to avoid actual prompt blocking
    mock_repl = mocker.patch("agent.repl.UniversalREPL.start_interactive_session")
    
    result = runner.invoke(app)
    
    # Assert the mock was called
    mock_repl.assert_called_once()
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_default.py -v`
Expected: FAIL (The help menu is shown, mock is not called)

- [ ] **Step 3: Write minimal implementation in `cli.py`**

```python
# In cli.py, below the other @app.command() declarations

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Lios-Agent: The Autonomous iOS Engineer CLI.
    Run without commands to enter interactive mode.
    """
    if ctx.invoked_subcommand is None:
        UniversalREPL.start_interactive_session()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_default.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli_default.py cli.py
git commit -m "feat: route default lios execution to interactive REPL"
```

---

### Task 2: Implement Interactive Session Loop with Slash Commands

**Files:**
- Modify: `agent/repl.py`
- Modify: `requirements.txt` (if `prompt_toolkit` is not installed, though it likely is. Verify first.)

- [ ] **Step 1: Check/Add dependencies**

Ensure `prompt_toolkit` is in `requirements.txt`. Add it if not.
```bash
# Example if needed:
# echo "prompt_toolkit" >> requirements.txt
# pip install prompt_toolkit
```

- [ ] **Step 2: Implement `start_interactive_session` shell in `agent/repl.py`**

```python
# Add imports at the top of agent/repl.py
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
import shlex
import sys

# ... inside UniversalREPL class ...

    @staticmethod
    def start_interactive_session():
        """
        Starts the default interactive REPL loop.
        """
        style = Style.from_dict({
            'prompt': 'ansicyan bold',
        })
        session = PromptSession(style=style)
        
        console.print("[bold green]Welcome to Lios-Agent Interactive Mode.[/bold green]")
        console.print("Type [bold]/help[/bold] to see available commands or just start chatting.")
        
        # We will need chat history here for Task 3
        chat_history = []
        
        while True:
            try:
                user_input = session.prompt('lios> ')
                text = user_input.strip()
                
                if not text:
                    continue
                    
                if text.startswith('/'):
                    # Command Routing
                    parts = shlex.split(text)
                    command = parts[0].lower()
                    args = parts[1:]
                    
                    if command in ['/exit', '/quit']:
                        console.print("[yellow]Goodbye![/yellow]")
                        break
                    elif command == '/help':
                        console.print("Available commands: /epic <name>, /story <epic> <id>, /execute <vault>, /board, /exit")
                    elif command == '/epic':
                        if len(args) >= 1:
                            # Import here to avoid circular dependencies if any
                            from cli import epic
                            epic(name=args[0])
                        else:
                            console.print("[red]Usage: /epic <name>[/red]")
                    elif command == '/story':
                        if len(args) >= 2:
                            from cli import story
                            story(epic_name=args[0], story_id=args[1])
                        else:
                            console.print("[red]Usage: /story <epic_name> <story_id>[/red]")
                    elif command == '/execute':
                        if len(args) >= 1:
                            from cli import execute
                            # We wrap execute since it runs asyncio.run internally, 
                            # calling it directly is fine as it spins up its own event loop
                            execute(vault_path=args[0])
                        else:
                            console.print("[red]Usage: /execute <vault_path>[/red]")
                    elif command == '/board':
                        console.print(Panel("[bold green]Trello integration coming soon![/bold green]\n\nFetching tasks from your remote board...", title="[bold blue]/board[/bold blue]"))
                    else:
                        console.print(f"[red]Unknown command:[/red] {command}")
                else:
                    # Proceed to chat (Implemented in Task 3)
                    UniversalREPL._handle_chat(text, chat_history)
                    
            except KeyboardInterrupt:
                continue
            except EOFError:
                console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
```

- [ ] **Step 3: Test loop locally (manual verification since it relies on I/O)**

Run: `python3 cli.py`
Expected: Drops into `lios>` prompt. Test `/help` and `/exit`.

- [ ] **Step 4: Commit**

```bash
git add agent/repl.py
git commit -m "feat: implement prompt_toolkit repl with slash command routing"
```

---

### Task 3: Implement Conversational Chat

**Files:**
- Modify: `agent/repl.py`

- [ ] **Step 1: Implement `_handle_chat` method**

```python
# Add to UniversalREPL class

    @staticmethod
    def _handle_chat(text: str, history: list):
        """
        Handles natural language input in the REPL using LangChain.
        """
        from agent.llm_factory import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        
        try:
            llm = get_llm(role="planning") # Use planning LLM for general chat
        except Exception as e:
            console.print(f"[bold red]Failed to initialize LLM:[/bold red] {e}")
            return
            
        if not history:
            # Initialize history with system prompt
            system_prompt = SystemMessage(content="""You are Lios, an Autonomous iOS Engineer.
The user is talking to you via your interactive CLI mode.
You can help them brainstorm, explain how to use the CLI, or answer general questions.
The available CLI commands are: /epic <name>, /story <epic> <id>, /execute <vault>, /board.
Keep your answers concise, helpful, and formatted in markdown.""")
            history.append(system_prompt)
            
        # Parse for @mentions
        parsed_input = UniversalREPL.parse_input(text, workspace_root=".")
        history.append(HumanMessage(content=parsed_input))
        
        try:
            with console.status("[dim]Thinking...[/dim]"):
                response = llm.invoke(history)
            
            ai_text = response.content
            UniversalREPL.print_agent_message(ai_text)
            history.append(AIMessage(content=ai_text))
            
        except Exception as e:
            console.print(f"[bold red]LLM Error:[/bold red] {e}")
            # Remove the failed human message from history
            history.pop()
```

- [ ] **Step 2: Commit**

```bash
git add agent/repl.py
git commit -m "feat: add conversational LLM chat to REPL"
```