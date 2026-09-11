"""
LangGraph workflow: the complete code review graph.

Graph topology (Phase 2 — parallel reviewers):

    START
      |
      v
  parse_diff
      |
      v
  build_context
      |
  +---+---+
  |       |
  v       v
correctness  security
  review    review
  |       |
  +---+---+
      |
      v
  merge_findings
      |
      v
  validate_findings
      |
      v
     END

The fan-out (build_context → correctness + security) and fan-in
(correctness + security → merge_findings) implement true LangGraph
parallelism. Both reviewers receive the same context independently.

Adding a third reviewer (e.g., performance) requires only:
  1. A new reviewer node returning {reviewer_raw_findings: [...]}
  2. A new add_edge(build_context → performance_review)
  3. A new add_edge(performance_review → merge_findings)
  4. Updating merge_findings_node to include the new key.

The linter / deterministic checker follows the same pattern.
"""
import logging

from langgraph.graph import StateGraph, START, END

from sentinel.graph.state import ReviewState
from sentinel.graph.nodes.diff_parser_node import parse_diff_node
from sentinel.graph.nodes.context_builder_node import build_context_node
from sentinel.graph.nodes.correctness_reviewer_node import correctness_review_node
from sentinel.graph.nodes.security_reviewer_node import security_review_node
from sentinel.graph.nodes.merge_findings_node import merge_findings_node
from sentinel.graph.nodes.validate_findings_node import validate_findings_node

logger = logging.getLogger(__name__)


def build_review_graph():
    """Build and compile the parallel code review LangGraph workflow.

    Returns:
        A compiled LangGraph that accepts ReviewState as input.
    """
    graph = StateGraph(ReviewState)

    # Register all nodes
    graph.add_node("parse_diff", parse_diff_node)
    graph.add_node("build_context", build_context_node)
    graph.add_node("correctness_review", correctness_review_node)
    graph.add_node("security_review", security_review_node)
    graph.add_node("merge_findings", merge_findings_node)
    graph.add_node("validate_findings", validate_findings_node)

    # Sequential preamble
    graph.add_edge(START, "parse_diff")
    graph.add_edge("parse_diff", "build_context")

    # Fan-out: both reviewers start simultaneously after build_context
    graph.add_edge("build_context", "correctness_review")
    graph.add_edge("build_context", "security_review")

    # Fan-in: merge waits for both reviewers to complete
    graph.add_edge("correctness_review", "merge_findings")
    graph.add_edge("security_review", "merge_findings")

    # Final validation gate
    graph.add_edge("merge_findings", "validate_findings")
    graph.add_edge("validate_findings", END)

    compiled = graph.compile()
    logger.debug("Review graph compiled: 6 nodes (correctness + security in parallel)")
    return compiled


# Module-level singleton — compiled once at import time
review_graph = build_review_graph()
