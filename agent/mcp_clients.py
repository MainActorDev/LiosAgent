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
        
    async def connect_and_get_tools(self, workspace_path: str = None) -> List:
        all_tools = []
        workspace_env = os.environ.copy()
        # Ensure common bin paths are available for subprocess resolution
        extra_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
        # Add NVM fallback optionally
        home = os.path.expanduser("~")
        extra_paths.extend([f"{home}/.local/bin", f"{home}/.cargo/bin", f"{home}/.nvm/versions/node/v18.17.0/bin"])
        
        workspace_env["PATH"] = workspace_env.get("PATH", "") + ":" + ":".join(extra_paths)
        
        if workspace_path:
            workspace_env["PWD"] = workspace_path
            
        server_configs = [
            ("XcodeBuildMCP", "npx", ["-y", "xcodebuildmcp@latest", "mcp"]),
            ("SerenaMCP", "serena", ["mcp"])
            # 3. Jira & Figma MCP (Placeholders for enterprise env variables)
        ]
        
        for name, cmd, args in server_configs:
            try:
                params = StdioServerParameters(command=cmd, args=args, env=workspace_env)
                stdio_transport = await self._exit_stack.enter_async_context(stdio_client(params))
                read, write = stdio_transport
                session = await self._exit_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                
                # load_mcp_tools automatically bridges the MCP protocol to LangChain Tool objects
                tools = await load_mcp_tools(session)
                print(f"✅ Activated {len(tools)} tools from {name}")
                all_tools.extend(tools)
                self.sessions.append(session)
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
