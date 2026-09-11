"""
Context builder: assembles LLM-ready context blocks for each diff hunk.

Context strategy (MVP):
    For each diff hunk → retrieve window_lines before and after from MCP → 
    combine with raw hunk diff → produce ContextBlock.

This is the designated extension point for future strategies:
    - Function-boundary extraction (AST-aware windowing)
    - Call-graph traversal (include callers/callees)
    - Type-aware context (include type definitions)
    - Test-aware context (include relevant test files)

Token budget (MVP): simple truncation when total estimated tokens exceed max_tokens.
Future: ranked prioritization by change significance, test coverage, call distance.
"""
import logging
from typing import TYPE_CHECKING

from sentinel.schemas.context import ContextBlock, ContextBudget
from sentinel.schemas.diff import DiffHunk

if TYPE_CHECKING:
    from sentinel.mcp.client import MCPClientInterface

logger = logging.getLogger(__name__)

# Rough token estimate: 1 token ≈ 4 characters
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character count.
    
    This is a fast approximation (not tiktoken). Sufficient for budget decisions.
    """
    return max(1, len(text) // _CHARS_PER_TOKEN)


class ContextBuilder:
    """Builds LLM-ready ContextBlocks from diff hunks.
    
    Each ContextBlock contains:
    - The raw hunk diff (what changed)
    - Surrounding source lines (context for understanding the change)
    
    Uses the MCP client to fetch file content — never reads files directly.
    """

    def __init__(
        self, mcp_client: "MCPClientInterface", budget: ContextBudget
    ) -> None:
        self.mcp_client = mcp_client
        self.budget = budget

    async def build(
        self, hunks: list[DiffHunk], repo_path: str
    ) -> list[ContextBlock]:
        """Build context blocks for all hunks, respecting token budget.
        
        Args:
            hunks: All diff hunks to build context for.
            repo_path: Absolute path to the repository.
            
        Returns:
            List of ContextBlocks, trimmed to stay within budget.
        """
        if not hunks:
            return []

        blocks: list[ContextBlock] = []
        total_tokens = 0

        for hunk in hunks:
            block = await self._build_single(hunk, repo_path)
            hunk_tokens = _estimate_tokens(block.surrounding_code + block.hunk_diff)

            # Per-file limit: if this single block exceeds the per-file limit, truncate it
            if hunk_tokens > self.budget.per_file_limit:
                block = self._truncate_block(block, self.budget.per_file_limit)
                hunk_tokens = _estimate_tokens(block.surrounding_code + block.hunk_diff)

            # Total budget: if adding this block would exceed total, stop
            if total_tokens + hunk_tokens > self.budget.max_tokens:
                logger.warning(
                    "Context budget exhausted at hunk %d/%d (total tokens ~%d). "
                    "Remaining hunks will not have surrounding context.",
                    len(blocks) + 1,
                    len(hunks),
                    total_tokens,
                )
                # Add a minimal block (hunk diff only) to preserve the diff signal
                minimal = ContextBlock(
                    file_path=hunk.file_path,
                    hunk_new_start=hunk.new_start,
                    hunk_new_end=hunk.new_start + hunk.new_count,
                    surrounding_code="[Context omitted: token budget exhausted]",
                    hunk_diff=hunk.hunk_text,
                    line_offset=hunk.new_start,
                )
                blocks.append(minimal)
                continue

            blocks.append(block)
            total_tokens += hunk_tokens

        logger.debug(
            "Built %d context blocks, estimated ~%d tokens", len(blocks), total_tokens
        )
        return blocks

    async def _build_single(self, hunk: DiffHunk, repo_path: str) -> ContextBlock:
        """Build one ContextBlock for one hunk.
        
        Fetches surrounding lines via MCP. Falls back to hunk-only if MCP fails.
        Also attempts to identify the changed symbol and fetches its references
        via the find_references MCP tool, adding them to the context to aid the LLM.
        """
        import re
        import json
        
        window = self.budget.window_lines
        start_line = max(1, hunk.new_start - window)
        end_line = hunk.new_start + hunk.new_count + window

        try:
            surrounding_code = await self.mcp_client.read_file(
                repo_path=repo_path,
                file_path=hunk.file_path,
                start_line=start_line,
                end_line=end_line,
            )
            
            # Extract symbol from diff hunk header
            # Pattern matches e.g. @@ ... @@ def parse(self... -> "parse"
            symbol_match = re.search(r"@@.*?@@.*?(?:(?:async\s+)?def|class)\s+([a-zA-Z_][a-zA-Z0-9_]*)", hunk.hunk_text)
            if symbol_match:
                symbol = symbol_match.group(1)
                
                # Fetch references using the new MCP tool
                try:
                    ref_output = await self.mcp_client.find_references(repo_path, symbol)
                    ref_data = json.loads(ref_output)
                    refs = ref_data.get("references", [])
                    
                    if refs:
                        MAX_REFERENCES = 5  # Cap the number of retrieved references to prevent context blowout
                        refs = refs[:MAX_REFERENCES]
                        
                        surrounding_code += f"\n\n--- Usage References for '{symbol}' (max {MAX_REFERENCES}) ---\n"
                        for ref in refs:
                            ref_file = ref.get('file')
                            ref_line = ref.get('line')
                            ref_kind = ref.get('kind')
                            
                            # Read a small bounded context around the reference
                            ref_code = await self.mcp_client.read_file(
                                repo_path=repo_path,
                                file_path=ref_file,
                                start_line=max(1, ref_line - 2),
                                end_line=ref_line + 2,
                            )
                            surrounding_code += f"\nFile: {ref_file} | Line: {ref_line} | Kind: {ref_kind}\n"
                            surrounding_code += f"{ref_code}\n"
                except Exception as ref_exc:
                    logger.warning("find_references failed or parsing failed for %s: %s", symbol, ref_exc)
                    
        except Exception as exc:
            logger.warning(
                "MCP read_file failed for %s (L%d-L%d): %s. Using hunk-only context.",
                hunk.file_path,
                start_line,
                end_line,
                exc,
            )
            surrounding_code = hunk.hunk_text

        return ContextBlock(
            file_path=hunk.file_path,
            hunk_new_start=hunk.new_start,
            hunk_new_end=hunk.new_start + hunk.new_count,
            surrounding_code=surrounding_code,
            hunk_diff=hunk.hunk_text,
            line_offset=start_line,
        )

    def _truncate_block(self, block: ContextBlock, max_tokens: int) -> ContextBlock:
        """Truncate surrounding_code to fit within per_file_limit."""
        max_chars = max_tokens * _CHARS_PER_TOKEN
        if len(block.surrounding_code) > max_chars:
            truncated = block.surrounding_code[:max_chars] + "\n... [truncated]"
            return block.model_copy(update={"surrounding_code": truncated})
        return block
