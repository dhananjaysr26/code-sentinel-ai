"""
Django ORM models for CodeSentinel AI.

Review: one review request (repo + refs).
ReviewFinding: one finding within a review, with user feedback.

SQLite is the default database. No external DB required for MVP.
"""
import uuid
from django.db import models


class Review(models.Model):
    """Represents one code review run."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repo_path = models.TextField(help_text="Absolute path to the local git repository")
    base_ref = models.CharField(max_length=256)
    target_ref = models.CharField(max_length=256)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    raw_diff = models.TextField(blank=True, default="")
    errors = models.JSONField(default=list, blank=True)
    review_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Review({self.id}, {self.status}, {self.base_ref}..{self.target_ref})"


class ReviewFinding(models.Model):
    """A single finding within a Review, with optional user feedback."""

    class Feedback(models.TextChoices):
        NONE = "none", "None"
        ACCEPT = "accept", "Accept"
        DISMISS = "dismiss", "Dismiss"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(
        Review, related_name="findings", on_delete=models.CASCADE
    )
    file = models.TextField()
    line = models.IntegerField(null=True, blank=True)
    title = models.TextField()
    category = models.CharField(max_length=64)
    severity = models.CharField(max_length=16)
    confidence = models.FloatField()
    explanation = models.TextField()
    evidence = models.TextField()
    suggested_fix = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=32, default="llm")
    subcategory = models.CharField(max_length=100, blank=True, default="")
    reviewer = models.CharField(max_length=50, blank=True, default="")
    feedback = models.CharField(
        max_length=16, choices=Feedback.choices, default=Feedback.NONE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-confidence"]

    def __str__(self) -> str:
        return f"Finding({self.id}, {self.severity}, {self.file}:{self.line})"

class ReviewUsage(models.Model):
    """Aggregate usage metadata for a review."""
    review = models.OneToOneField(Review, related_name="usage", on_delete=models.CASCADE)
    provider = models.CharField(max_length=64)
    
    llm_calls = models.IntegerField(default=0)
    mcp_calls = models.IntegerField(default=0)
    unique_mcp_calls = models.IntegerField(default=0)
    duplicate_mcp_calls = models.IntegerField(default=0)
    agent_iterations = models.IntegerField(default=0)
    langgraph_node_executions = models.IntegerField(default=0)
    
    retry_count = models.IntegerField(default=0)
    fallback_count = models.IntegerField(default=0)
    timeout_count = models.IntegerField(default=0)
    
    total_input_tokens = models.IntegerField(default=0)
    total_output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    
    total_latency_ms = models.IntegerField(default=0)
    llm_latency_ms = models.IntegerField(default=0)
    mcp_latency_ms = models.IntegerField(default=0)
    critical_path_latency_ms = models.IntegerField(default=0)
    
    total_estimated_cost = models.FloatField(null=True, blank=True)
    models_used = models.JSONField(default=list, blank=True)
    finalization_reason = models.CharField(max_length=64, default="unknown")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Usage({self.review_id}, {self.total_tokens} tokens)"

class LLMCallUsage(models.Model):
    """Usage details for a specific LLM invocation during a review."""
    review = models.ForeignKey(Review, related_name="reviewer_usage", on_delete=models.CASCADE)
    reviewer = models.CharField(max_length=64)
    provider = models.CharField(max_length=64)
    model = models.CharField(max_length=128)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    latency_ms = models.IntegerField(default=0)
    estimated_cost = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=32, default="success")
    phase = models.CharField(max_length=64, blank=True)
    message_count = models.IntegerField(default=0)
    source_code_tokens = models.IntegerField(default=0)
    diff_tokens = models.IntegerField(default=0)
    system_prompt_tokens = models.IntegerField(default=0)
    reviewer_prompt_tokens = models.IntegerField(default=0)
    tool_schema_tokens = models.IntegerField(default=0)
    history_tokens = models.IntegerField(default=0)
    tool_result_tokens = models.IntegerField(default=0)
    structured_schema_tokens = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"CallUsage({self.reviewer}, {self.total_tokens} tokens)"
