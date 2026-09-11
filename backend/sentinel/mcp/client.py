"""
MCP client: communicates with the CodeSentinel MCP server via stdio.

Architecture:
    LangGraph node → StdioMCPClient → MCPServer (subprocess) → Git/filesystem

The client is the ONLY way the LangGraph pipeline accesses repository data.
This boundary ensures the architecture cleanly demonstrates:
    agent → MCP client → MCP server → repository
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class MCPClientInterface(ABC):
    """Abstract interface for MCP tool calls.
    
    Concrete implementations: StdioMCPClient (production), MockMCPClient (tests).
    """

    @abstractmethod
    async def get_diff(
        self, repo_path: str, base_ref: str, target_ref: str
    ) -> str:
        """Get git diff between two refs."""
        ...

    @abstractmethod
    async def read_file(
        self, repo_path: str, file_path: str, start_line: int, end_line: int
    ) -> str:
        """Read a line range from a file in the repository."""
        ...


class StdioMCPClient(MCPClientInterface):
    """Communicates with the MCP server process via stdio transport.
    
    Each tool call spawns the MCP server, sends an initialize + call_tool
    message pair, and returns the result. This is correct MCP protocol
    behavior for a stdio-transport server.
    
    In production, the server script is set via MCP_SERVER_SCRIPT env var.
    """

    def __init__(self, server_script: str) -> None:
        """
        Args:
            server_script: Absolute path to mcp_server/server.py.
        """
        self.server_script = server_script
        logger.debug("StdioMCPClient initialized with server: %s", server_script)

    async def _call_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute one MCP tool call via stdio transport.
        
        Uses the mcp library's stdio_client context manager which handles
        the MCP initialize handshake automatically.
        
        Args:
            tool_name: Name of the tool to call.
            arguments: Tool input arguments.
            
        Returns:
            Text content from the tool response.
            
        Raises:
            RuntimeError: If the MCP call fails.
        """
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command="python",
            args=[self.server_script],
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)

                    # Extract text from result content
                    if result.content and len(result.content) > 0:
                        content = result.content[0]
                        if hasattr(content, "text"):
                            return content.text
                    return ""
        except Exception as exc:
            logger.error("MCP tool call %r failed: %s", tool_name, exc)
            raise RuntimeError(f"MCP tool {tool_name!r} failed: {exc}") from exc

    async def get_diff(
        self, repo_path: str, base_ref: str, target_ref: str
    ) -> str:
        """Get git diff via MCP server."""
        logger.debug(
            "MCP get_diff: %s %s..%s", repo_path, base_ref, target_ref
        )
        return await self._call_tool(
            "get_diff",
            {
                "repo_path": repo_path,
                "base_ref": base_ref,
                "target_ref": target_ref,
            },
        )

    async def read_file(
        self, repo_path: str, file_path: str, start_line: int, end_line: int
    ) -> str:
        """Read file lines via MCP server."""
        logger.debug(
            "MCP read_file: %s/%s L%d-L%d", repo_path, file_path, start_line, end_line
        )
        return await self._call_tool(
            "read_file",
            {
                "repo_path": repo_path,
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
            },
        )
