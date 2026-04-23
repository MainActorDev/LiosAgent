import os
import typer
from rich.console import Console
from rich.panel import Panel
import asyncio
from dotenv import load_dotenv

from agent.repl import UniversalREPL

app = typer.Typer(
    help="Lios-Agent: The Autonomous iOS Engineer CLI",
    add_completion=False,
)
console = Console()

@app.command()
def epic(
    name: str = typer.Argument(..., help="The name of the Epic to generate (e.g., habit-tracker)"),
    context: list[str] = typer.Option(None, "--context", "-c", help="Paths to context files (e.g., prd.md)")
):
    """
    Initialize a full Epic Vault and begin the Interactive Architecture Planning phase.
    """
    console.print(Panel.fit(f"[bold blue]Initializing Epic Vault:[/bold blue] [green]{name}[/green]", border_style="blue"))
    
    from agent.vault_manager import VaultManager
    vault_path = VaultManager.create_epic_vault(name)
    
    console.print("[dim]Starting interactive intake session...[/dim]")
    UniversalREPL.print_agent_message("Hello! I am ready to architect your new Epic. Please provide your PRD or describe what we are building. You can mention files using `@path/to/file`.")
    
    instructions = UniversalREPL.chat_loop(prompt_text="You", workspace_root=".")
    
    # Write the initial state out
    state = {
        "task_id": name,
        "instructions": instructions,
        "retries_count": 0,
        "history": []
    }
    VaultManager.dump_human_readable_state(vault_path, state)
    
    console.print(f"\n[bold green]Epic Vault initialized at:[/bold green] {vault_path}")
    console.print(f"Run `lios execute {vault_path}` to begin architectural planning!")

@app.command()
def story(
    epic_name: str = typer.Argument(..., help="The parent Epic name"),
    story_id: str = typer.Argument(..., help="The ID of the Story to generate (e.g., login-bug)"),
    context: list[str] = typer.Option(None, "--context", "-c", help="Paths to context files")
):
    """
    Initialize a standalone Story Vault and begin the Interactive Planning phase.
    """
    console.print(Panel.fit(f"[bold blue]Initializing Story Vault:[/bold blue] [green]{epic_name}/{story_id}[/green]", border_style="blue"))
    
    from agent.vault_manager import VaultManager
    vault_path = VaultManager.create_story_vault(epic_name, story_id)
    
    console.print("[dim]Starting interactive intake session...[/dim]")
    UniversalREPL.print_agent_message(f"Hello! I am ready to architect Story `{story_id}`. Please describe the task. You can mention files using `@path/to/file`.")
    
    instructions = UniversalREPL.chat_loop(prompt_text="You", workspace_root=".")
    
    state = {
        "task_id": story_id,
        "instructions": instructions,
        "retries_count": 0,
        "history": []
    }
    VaultManager.dump_human_readable_state(vault_path, state)
    
    console.print(f"\n[bold green]Story Vault initialized at:[/bold green] {vault_path}")
    console.print(f"Run `lios execute {vault_path}` to begin architectural planning!")

@app.command()
def execute(
    vault_path: str = typer.Argument(..., help="Path to the Epic or Story vault to execute")
):
    """
    Execute an approved Architectural Blueprint from a specific Vault.
    """
    if not os.path.exists(vault_path):
        console.print(f"[bold red]Error:[/bold red] Vault path '{vault_path}' does not exist.")
        raise typer.Exit(code=1)
        
    from agent.vault_manager import VaultManager
    from agent.graph import build_graph
    import asyncio
    
    checkpointer = VaultManager.get_checkpointer(vault_path)
    graph_app = build_graph(checkpointer=checkpointer)
    
    console.print(Panel.fit(f"[bold green]Executing Vault:[/bold green] [yellow]{vault_path}[/yellow]", border_style="green"))
    
    # Derive epic_name from the vault path (assuming .lios/epics/<epic_name>)
    epic_name = os.path.basename(os.path.normpath(vault_path))
    
    # Start the async execution loop
    async def run_graph():
        config = {"configurable": {"thread_id": epic_name}}
        
        # Load initial instructions from the vault's state.yml if this is the first run
        import yaml
        state_yml_path = os.path.join(vault_path, "state.yml")
        initial_state = None
        
        # Check if LangGraph already has state for this thread
        current_state = await graph_app.aget_state(config)
        if not current_state or not current_state.values:
            if os.path.exists(state_yml_path):
                with open(state_yml_path, "r") as f:
                    initial_state = yaml.safe_load(f)
            else:
                console.print("[bold red]No state.yml found. Did you run `lios init epic` first?[/bold red]")
                return
                
        # Main Execution Loop
        while True:
            try:
                # If we have initial state and haven't started, pass it. Otherwise pass None to resume.
                input_state = initial_state if (not current_state or not current_state.values) else None
                
                await graph_app.ainvoke(input_state, config=config)
                
                # After ainvoke completes or yields, check the state
                current_state = await graph_app.aget_state(config)
                
                # Dump human readable state to vault
                if current_state and current_state.values:
                    VaultManager.dump_human_readable_state(vault_path, current_state.values)
                
                if not current_state.next:
                    console.print("\n[bold green]🎉 Workflow Completed![/bold green]")
                    break
                    
                # Handle Interrupts (Human in the loop)
                next_node = current_state.next[0]
                
                if next_node == "blueprint_approval_gate":
                    UniversalREPL.print_agent_message("The Architectural Blueprint has been generated. Please review `blueprint.md` in your vault.\nType **Approve** to begin coding, or provide feedback to regenerate the blueprint.")
                    feedback = UniversalREPL.chat_loop()
                    
                    if "approve" in feedback.lower():
                        await graph_app.aupdate_state(config, {"history": ["Blueprint approved by human, proceeding..."]})
                    else:
                        old_instructions = current_state.values.get("instructions", "")
                        new_instructions = old_instructions + f"\n\n[Blueprint Feedback]:\n{feedback}"
                        await graph_app.aupdate_state(config, {
                            "instructions": new_instructions, 
                            "history": ["Feedback received. Regenerating architecture plan."]
                        })
                
                elif next_node == "await_clarification":
                    UniversalREPL.print_agent_message("I am stuck and need clarification or human intervention.")
                    feedback = UniversalREPL.chat_loop()
                    old_instructions = current_state.values.get("instructions", "")
                    new_instructions = old_instructions + f"\n\n[Developer Clarification]:\n{feedback}"
                    await graph_app.aupdate_state(config, {
                        "instructions": new_instructions,
                        "halted": False,
                        "compiler_errors": []
                    })
                
                elif next_node == "push":
                    UniversalREPL.print_agent_message("Validation complete or aborted. Ready to push to GitHub?")
                    feedback = UniversalREPL.chat_loop("Push? [y/N]")
                    if "y" in feedback.lower():
                        # Let it proceed to push
                        pass
                    else:
                        console.print("[yellow]Push aborted. Halting.[/yellow]")
                        break
                        
            except Exception as e:
                console.print(f"\n[bold red]Fatal Graph Error:[/bold red] {e}")
                import traceback
                traceback.print_exc()
                break

    asyncio.run(run_graph())

if __name__ == "__main__":
    app()
