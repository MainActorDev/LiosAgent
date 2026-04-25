import os
import re
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
import shlex
import sys
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown
from pygments.lexer import RegexLexer
from pygments.token import Token

console = Console()

class LiosLexer(RegexLexer):
    name = 'Lios'
    aliases = ['lios']
    filenames = []

    tokens = {
        'root': [
            (r'^/\w+', Token.Keyword),        # Slash commands
            (r'@[\w./-]+', Token.Name.Class), # File paths
            (r'[^/@\n]+', Token.Text),        # Standard text
            (r'.', Token.Text),               # Fallback
        ]
    }

class UniversalREPL:
    """
    Handles interactive terminal sessions and parses special commands like @file.
    """

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

    @staticmethod
    def start_interactive_session():
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.lexers import PygmentsLexer
        from prompt_toolkit.styles import Style as PromptStyle
        import os
        
        console.print(Panel.fit("[bold green]Welcome to the Lios-Agent REPL![/bold green]\nType [cyan]/help[/cyan] for commands or start chatting.", title="Lios", border_style="green"))
        
        # Setup history
        config_dir = os.path.expanduser("~/.config/lios")
        try:
            os.makedirs(config_dir, exist_ok=True)
            history_file = os.path.join(config_dir, ".lios_history")
            history = FileHistory(history_file)
        except Exception as e:
            console.print(f"[bold yellow]Warning: Could not initialize history file ({e})[/bold yellow]")
            history = None

        style = PromptStyle.from_dict({
            'prompt': 'bold cyan',
            'pygments.keyword': 'cyan',
            'pygments.name.class': 'green',
        })
        
        session = PromptSession(
            history=history,
            lexer=PygmentsLexer(LiosLexer),
            style=style
        )
        
        # We will need chat history here for Task 3
        chat_history = []
        
        while True:
            try:
                # Use the session to prompt
                user_input = session.prompt([('class:prompt', 'lios> ')])
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

    @staticmethod
    def parse_input(user_input: str, workspace_root: str = ".") -> str:
        """
        Parses the user input for @file syntax.
        If a file is mentioned, it reads the file and appends its content to the prompt.
        """
        # Regex to find @filepath (allows alphanumeric, dots, slashes, dashes, underscores)
        # It stops at whitespace.
        pattern = r'@([a-zA-Z0-9_./-]+)'
        matches = re.findall(pattern, user_input)
        
        if not matches:
            return user_input
            
        compiled_input = user_input + "\n\n### Injected Context from @mentions:\n"
        
        for filepath in set(matches):
            full_path = os.path.join(workspace_root, filepath)
            if os.path.isfile(full_path):
                try:
                    with open(full_path, "r") as f:
                        content = f.read()
                    compiled_input += f"\n--- {filepath} ---\n```\n{content}\n```\n"
                    console.print(f"[dim]📎 Attached {filepath}[/dim]")
                except Exception as e:
                    console.print(f"[bold red]⚠️ Failed to read {filepath}:[/bold red] {e}")
                    compiled_input += f"\n--- {filepath} (ERROR) ---\nCould not read file.\n"
            else:
                console.print(f"[bold yellow]⚠️ File not found:[/bold yellow] {filepath}")
                compiled_input += f"\n--- {filepath} (NOT FOUND) ---\n"
                
        return compiled_input

    @staticmethod
    def single_prompt(prompt_text: str = "You", workspace_root: str = ".") -> str:
        """
        A single turn prompt that handles slash commands.
        Returns the parsed instruction string.
        """
        while True:
            try:
                user_input = Prompt.ask(f"[bold cyan]{prompt_text}[/bold cyan]")
                
                if not user_input.strip():
                    continue
                    
                if user_input.strip() == "/exit":
                    console.print("[yellow]Exiting session...[/yellow]")
                    exit(0)
                    
                # You can add more slash commands here like /rollback
                if user_input.strip() == "/rollback":
                    console.print("[bold red]Rollback not yet implemented.[/bold red]")
                    continue

                if user_input.strip() == "/board":
                    console.print(Panel("[bold green]Trello integration coming soon![/bold green]\n\nFetching tasks from your remote board...", title="[bold blue]/board[/bold blue]"))
                    continue

                parsed_input = UniversalREPL.parse_input(user_input, workspace_root)
                return parsed_input
                
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Session aborted by user.[/yellow]")
                exit(0)

    @staticmethod
    def interactive_intake_session(epic_name: str, workspace_root: str = ".") -> str:
        """
        Boots up an LLM-backed interactive conversation to refine requirements.
        Returns the concatenated chat history + file context.
        """
        from agent.llm_factory import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        
        try:
            llm = get_llm(role="planning")
        except Exception as e:
            console.print(f"[bold red]Failed to initialize LLM for REPL:[/bold red] {e}")
            # Fallback to single prompt
            return UniversalREPL.single_prompt("You", workspace_root)
            
        system_prompt = SystemMessage(content="""You are an expert iOS Product Manager. The user wants to build a new feature.
They will provide an initial PRD or description. Ask clarifying questions until you have enough detail to write a comprehensive technical PRD.
Do not write the PRD yet. Just ask 1-2 focused questions at a time to clarify the user's intent.
Once you have enough detail to proceed with architecture, or if the user explicitly says they are done, output exactly 'READY_TO_ARCHITECT' on a new line. Do not output this prematurely.""")

        messages = [system_prompt]
        accumulated_context = []
        
        while True:
            try:
                user_input = Prompt.ask(f"[bold cyan]You (type /done to finish)[/bold cyan]")
                
                if not user_input.strip():
                    continue
                    
                if user_input.strip() in ["/exit", "/done"]:
                    console.print("[yellow]Intake complete.[/yellow]")
                    break
                
                parsed_input = UniversalREPL.parse_input(user_input, workspace_root)
                accumulated_context.append(f"User: {parsed_input}")
                messages.append(HumanMessage(content=parsed_input))
                
                with console.status("[dim]Agent is thinking...[/dim]"):
                    response = llm.invoke(messages)
                    
                ai_text = response.content.strip()
                messages.append(AIMessage(content=ai_text))
                
                if "READY_TO_ARCHITECT" in ai_text:
                    clean_text = ai_text.replace("READY_TO_ARCHITECT", "").strip()
                    if clean_text:
                        UniversalREPL.print_agent_message(clean_text)
                        accumulated_context.append(f"Agent: {clean_text}")
                    break
                else:
                    UniversalREPL.print_agent_message(ai_text)
                    accumulated_context.append(f"Agent: {ai_text}")
                    
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Session aborted by user.[/yellow]")
                exit(0)
                
        return "\n\n".join(accumulated_context)

    @staticmethod
    def print_agent_message(message: str, title: str = "Lios-Agent"):
        """Prints a styled message from the agent."""
        console.print(Panel(Markdown(message), title=f"[bold purple]{title}[/bold purple]", border_style="purple"))
