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
    feedback = models.CharField(
        max_length=16, choices=Feedback.choices, default=Feedback.NONE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-confidence"]

    def __str__(self) -> str:
        return f"Finding({self.id}, {self.severity}, {self.file}:{self.line})"
