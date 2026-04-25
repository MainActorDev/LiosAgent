import os
import re
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

class UniversalREPL:
    """
    Handles interactive terminal sessions and parses special commands like @file.
    """
    
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
