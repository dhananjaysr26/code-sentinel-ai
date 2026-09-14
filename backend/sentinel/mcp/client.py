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
        
    @abstractmethod
    async def find_references(
        self, repo_path: str, symbol: str, path: str = None
    ) -> str:
        """Find usages/references to a symbol."""
        ...
        
    @abstractmethod
    async def run_linter(
        self, repo_path: str, path: str, revision: str = None
    ) -> str:
        """Run a deterministic lint tool against a repository file."""
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
        
        # Track number of MCP calls to support observability
        self.call_stats = {
            "get_diff": 0,
            "read_file": 0,
            "find_references": 0,
            "run_linter": 0
        }

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
        import sys

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script],
        )
        
        self.call_stats[tool_name] = self.call_stats.get(tool_name, 0) + 1

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

    async def find_references(
        self, repo_path: str, symbol: str, path: str = None
    ) -> str:
        """Find usages/references to a symbol via MCP server."""
        import time
        start_time = time.monotonic()
        logger.info(f"FIND_REFERENCES_START symbol={symbol}")
        
        args = {"repo_path": repo_path, "symbol": symbol}
        if path:
            args["path"] = path
            
        result = await self._call_tool("find_references", args)
        
        latency_ms = int((time.monotonic() - start_time) * 1000)
        
        import json
        try:
            data = json.loads(result)
            count = data.get("count", 0)
            if "error" in data:
                logger.error(f"FIND_REFERENCES_COMPLETE symbol={symbol} error={data['error']} latency_ms={latency_ms}")
            else:
                logger.info(f"FIND_REFERENCES_COMPLETE symbol={symbol} count={count} latency_ms={latency_ms}")
        except json.JSONDecodeError:
            logger.info(f"FIND_REFERENCES_COMPLETE symbol={symbol} latency_ms={latency_ms}")
            
        return result

    async def run_linter(
        self, repo_path: str, path: str, revision: str = None
    ) -> str:
        """Run a deterministic lint tool via MCP server."""
        import time
        start_time = time.monotonic()
        logger.info(f"LINTER_START path={path} tool=ruff")
        
        args = {
            "repo_path": repo_path,
            "path": path,
        }
        if revision is not None:
            args["revision"] = revision
            
        result = await self._call_tool(
            "run_linter",
            args,
        )
        
        latency_ms = int((time.monotonic() - start_time) * 1000)
        
        import json
        try:
            data = json.loads(result)
            success = data.get("success", False)
            issue_count = data.get("issue_count", 0)
            logger.info(f"LINTER_COMPLETE path={path} issues={issue_count} latency_ms={latency_ms} success={str(success).lower()}")
        except json.JSONDecodeError:
            logger.info(f"LINTER_COMPLETE path={path} latency_ms={latency_ms} success=false")
            
        return result
