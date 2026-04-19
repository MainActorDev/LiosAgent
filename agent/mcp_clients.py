import os
import asyncio
from typing import List, Optional, Set
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools

# Tools that are useful for the Coder agents (read, search, edit, shell)
CODER_TOOL_ALLOWLIST: Set[str] = {
    "read_file",
    "create_text_file",
    "list_dir",
    "find_file",
    "replace_content",
    "replace_lines",
    "search_for_pattern",
    "execute_shell_command",
    "get_symbols_overview",
    "find_symbol",
    "replace_symbol_body",
    "insert_after_symbol",
    "insert_before_symbol",
}

class MCPManager:
    """
    Discovery & Aggregation Layer for MCP tool servers.
    
    Supports two modes:
    - `planner` (default): Loads ALL tools from all configured servers for broad research.
    - `coder`: Loads ONLY Serena with a curated subset of editing tools for focused code generation.
    """
    def __init__(self):
        self._exit_stack = AsyncExitStack()
        self.sessions = []
        
    async def connect_and_get_tools(self, workspace_path: str = None, instructions: str = "", mode: str = "planner") -> List:
        all_tools = []
        workspace_env = os.environ.copy()
        
        # Resolve to absolute path to prevent Serena from indexing the wrong project
        abs_workspace = os.path.abspath(workspace_path) if workspace_path else None
        
        try:
            # Dynamically fetch the shell's true PATH to resolve nvm / correct node binaries safely.
            import subprocess
            shell_path = subprocess.check_output(["bash", "-l", "-c", "echo $PATH"]).decode().strip()
            workspace_env["PATH"] = shell_path
        except Exception as e:
            print(f"Fallback: Could not resolve interactive shell PATH. Using defaults. ({e})")
            extra_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
            home = os.path.expanduser("~")
            extra_paths.extend([f"{home}/.local/bin", f"{home}/.cargo/bin"])
            workspace_env["PATH"] = workspace_env.get("PATH", "") + ":" + ":".join(extra_paths)
        
        import shutil
        
        server_configs = []
        
        # --- SerenaMCP (available in both planner and coder modes) ---
        # We use `bash -c "cd <workspace> && uvx ..."` to guarantee Serena's CWD
        # is the target project, not the orchestrator's directory.
        uvx_path = shutil.which("uvx")
        if uvx_path and abs_workspace:
            serena_cmd = f"cd '{abs_workspace}' && {uvx_path} --from git+https://github.com/oraios/serena serena start-mcp-server --project-from-cwd --open-web-dashboard false"
            server_configs.append(("SerenaMCP", "bash", ["-c", serena_cmd]))
        elif not uvx_path:
            print("ℹ️ SerenaMCP skipped: `uvx` not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh")
            
        # --- XcodeBuildMCP, Figma, Jira (planner mode only) ---
        if mode == "planner":
            server_configs.append(("XcodeBuildMCP", "npx", ["-y", "xcodebuildmcp@latest", "mcp"]))
            
            instructions_lower = instructions.lower()
            has_jira_link = "atlassian.net" in instructions_lower or "jira" in instructions_lower
            
            if has_jira_link and os.environ.get("JIRA_API_TOKEN") and os.environ.get("JIRA_EMAIL") and os.environ.get("JIRA_BASE_URL"):
                server_configs.append(("JiraMCP", "npx", ["-y", "github:sooperset/mcp-atlassian"]))
        
        for name, cmd, args in server_configs:
            try:
                params = StdioServerParameters(command=cmd, args=args, env=workspace_env)
                
                # Enforce strict timeouts to prevent buggy packages from infinitely locking the stream
                stdio_transport = await asyncio.wait_for(
                    self._exit_stack.enter_async_context(stdio_client(params)), 
                    timeout=30.0
                )
                read, write = stdio_transport
                
                session = await asyncio.wait_for(
                    self._exit_stack.enter_async_context(ClientSession(read, write)),
                    timeout=15.0
                )
                
                await asyncio.wait_for(session.initialize(), timeout=15.0)
                
                # load_mcp_tools automatically bridges the MCP protocol to LangChain Tool objects
                tools = await asyncio.wait_for(load_mcp_tools(session), timeout=15.0)
                
                # In coder mode, filter to only the tools the coder actually needs
                if mode == "coder":
                    tools = [t for t in tools if t.name in CODER_TOOL_ALLOWLIST]
                    
                print(f"✅ Activated {len(tools)} tools from {name}: {[t.name for t in tools]}")
                all_tools.extend(tools)
                self.sessions.append(session)
            except asyncio.TimeoutError:
                print(f"⚠️ Timeout Error: MCP Server {name} hung indefinitely while connecting and was terminated.")
            except Exception as e:
                print(f"⚠️ Failed to connect to {name}: {e}")
                
        return all_tools
        
    async def cleanup(self):
        await self._exit_stack.aclose()

if __name__ == "__main__":
    async def run_test():
        print("Testing Context Aggregation Layer via MCPManager...")
        manager = MCPManager()
        try:
            tools = await manager.connect_and_get_tools()
            for t in tools:
                print(f"- {t.name}: {t.description[:60]}...")
        finally:
            await manager.cleanup()
            
    asyncio.run(run_test())
