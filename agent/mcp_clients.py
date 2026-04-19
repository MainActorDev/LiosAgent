import os
import asyncio
from typing import List
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools

class MCPManager:
    """
    Conceptually, this acts as the Discovery & Aggregation Layer.
    It initiates persistent connections to localized stdio MCP servers and translates
    their capabilities into LangChain-compatible tools that the Master Planner
    and Execution Squad can utilize natively.
    """
    def __init__(self):
        self._exit_stack = AsyncExitStack()
        self.sessions = []
        
    async def connect_and_get_tools(self, workspace_path: str = None, instructions: str = "") -> List:
        all_tools = []
        workspace_env = os.environ.copy()
        
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
        
        if workspace_path:
            workspace_env["PWD"] = workspace_path
            
        import shutil
        
        server_configs = [
            ("XcodeBuildMCP", "npx", ["-y", "xcodebuildmcp@latest", "mcp"]),
        ]
        
        # SerenaMCP requires `uvx` (from the `uv` Python toolchain) to be installed
        uvx_path = shutil.which("uvx")
        if uvx_path:
            server_configs.append(("SerenaMCP", uvx_path, ["serena", "mcp"]))
        else:
            print("ℹ️ SerenaMCP skipped: `uvx` not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh")
        
        # 3. Optional Enterprise Integrations (Figma & Jira)
        instructions_lower = instructions.lower()
        has_jira_link = "atlassian.net" in instructions_lower or "jira" in instructions_lower
        has_figma_link = "figma.com" in instructions_lower or "figma" in instructions_lower
        
        # Only use Jira MCP if Jira link is mentioned in Github Issue
        if has_jira_link and os.environ.get("JIRA_API_TOKEN") and os.environ.get("JIRA_EMAIL") and os.environ.get("JIRA_BASE_URL"):
            server_configs.append(("JiraMCP", "npx", ["-y", "github:sooperset/mcp-atlassian"]))
            
        # Only use Figma MCP if Figma link is mentioned in Github Issue OR Jira
        # (If Jira is loaded, we proactively load Figma so the agent can access Figma links found inside the Jira ticket)
        if (has_figma_link or has_jira_link) and os.environ.get("FIGMA_ACCESS_TOKEN"):
            server_configs.append(("FigmaMCP", "npx", ["-y", "github:glips/figma-context-mcp"]))
        
        for name, cmd, args in server_configs:
            try:
                params = StdioServerParameters(command=cmd, args=args, env=workspace_env)
                
                # Enforce strict timeouts linearly to prevent buggy packages from infinitely locking the stream
                stdio_transport = await asyncio.wait_for(
                    self._exit_stack.enter_async_context(stdio_client(params)), 
                    timeout=15.0
                )
                read, write = stdio_transport
                
                session = await asyncio.wait_for(
                    self._exit_stack.enter_async_context(ClientSession(read, write)),
                    timeout=15.0
                )
                
                await asyncio.wait_for(session.initialize(), timeout=15.0)
                
                # load_mcp_tools automatically bridges the MCP protocol to LangChain Tool objects
                tools = await asyncio.wait_for(load_mcp_tools(session), timeout=15.0)
                print(f"✅ Activated {len(tools)} tools from {name}")
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
