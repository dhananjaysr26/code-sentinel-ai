import asyncio
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from sentinel.graph.nodes.deterministic_checks_node import deterministic_checks_node
from sentinel.schemas.diff import DiffHunk

async def main():
    state = {
        "repo_path": "/Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/backend",
        "diff_hunks": [
            DiffHunk(
                file_path="sentinel/graph/state.py",
                old_start=1, old_count=1,
                new_start=1, new_count=1,
                hunk_text="",
                added_lines=[],
                removed_lines=[],
                changed_line_numbers=[]
            )
        ]
    }
    result = await deterministic_checks_node(state)
    print(result)

asyncio.run(main())
