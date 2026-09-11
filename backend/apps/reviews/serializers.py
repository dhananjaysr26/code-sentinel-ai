"""DRF serializers for Review and ReviewFinding models."""
from rest_framework import serializers
from .models import Review, ReviewFinding


class ReviewFindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewFinding
        fields = [
            "id", "file", "line", "title", "category",
            "severity", "confidence", "explanation", "evidence",
            "suggested_fix", "source", "feedback", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ReviewSerializer(serializers.ModelSerializer):
    findings = ReviewFindingSerializer(many=True, read_only=True)

    class Meta:
        model = Review
        fields = [
            "id", "repo_path", "base_ref", "target_ref", "status",
            "raw_diff", "errors", "review_metadata", "findings",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "raw_diff", "errors",
                            "review_metadata", "created_at", "updated_at"]


class ReviewCreateSerializer(serializers.Serializer):
    """Validates the POST /api/reviews/ request body."""
    repo_path = serializers.CharField(
        max_length=4096,
        help_text="Absolute path to the local git repository",
    )
    base_ref = serializers.CharField(
        max_length=256,
        help_text="Base git ref (e.g. HEAD~1, main)",
    )
    target_ref = serializers.CharField(
        max_length=256,
        help_text="Target git ref (e.g. HEAD, feature-branch)",
    )
    llm_provider = serializers.ChoiceField(
        choices=["openai", "bedrock"],
        default="openai",
        help_text="LLM provider to use for this review",
    )

    def validate_repo_path(self, value: str) -> str:
        from pathlib import Path
        path = Path(value).resolve()
        if not path.exists():
            raise serializers.ValidationError(
                f"Path does not exist: {value}"
            )
        return str(path)


class FeedbackSerializer(serializers.Serializer):
    """Validates the POST .../feedback/ request body."""
    action = serializers.ChoiceField(
        choices=["accept", "dismiss"],
        help_text="User feedback action: accept or dismiss",
    )
