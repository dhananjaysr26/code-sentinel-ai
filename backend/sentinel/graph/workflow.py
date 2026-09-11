"""
LangGraph workflow: the complete code review graph.

Graph topology:
  START → parse_diff → build_context → correctness_review → validate_findings → END

Each node has a single responsibility and is independently testable.

Future evolution (P1):
  START → parse_diff → build_context → [correctness_review ‖ security_review ‖ linter]
          → deduplicate → validate_findings → END
  (parallel fan-out with Send API or conditional edges)
"""
import logging

from langgraph.graph import StateGraph, START, END

from sentinel.graph.state import ReviewState
from sentinel.graph.nodes.diff_parser_node import parse_diff_node
from sentinel.graph.nodes.context_builder_node import build_context_node
from sentinel.graph.nodes.correctness_reviewer_node import correctness_review_node
from sentinel.graph.nodes.validate_findings_node import validate_findings_node

logger = logging.getLogger(__name__)


def build_review_graph():
    """Build and compile the code review LangGraph workflow.

    Returns:
        A compiled LangGraph that accepts ReviewState as input.
    """
    graph = StateGraph(ReviewState)

    graph.add_node("parse_diff", parse_diff_node)
    graph.add_node("build_context", build_context_node)
    graph.add_node("correctness_review", correctness_review_node)
    graph.add_node("validate_findings", validate_findings_node)

    graph.add_edge(START, "parse_diff")
    graph.add_edge("parse_diff", "build_context")
    graph.add_edge("build_context", "correctness_review")
    graph.add_edge("correctness_review", "validate_findings")
    graph.add_edge("validate_findings", END)

    compiled = graph.compile()
    logger.debug("Review graph compiled: 4 nodes")
    return compiled


# Module-level singleton — compiled once at import time
review_graph = build_review_graph()
