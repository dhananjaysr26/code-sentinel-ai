import queue
from collections import defaultdict
from typing import Dict, Any

# Simple in-memory global event bus for SSE.
# review_id -> Queue
_REVIEW_EVENTS: Dict[str, queue.Queue] = defaultdict(queue.Queue)

def publish_event(review_id: str, event_data: Dict[str, Any]):
    """Publish an event to a specific review's SSE stream."""
    _REVIEW_EVENTS[str(review_id)].put(event_data)

def get_event_queue(review_id: str) -> queue.Queue:
    """Get the queue for a specific review."""
    return _REVIEW_EVENTS[str(review_id)]
