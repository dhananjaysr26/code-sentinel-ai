"""
Django REST Framework views for CodeSentinel AI.

Design principle: views are thin HTTP adapters.
All domain logic lives in sentinel/ — NOT here.

Endpoints:
  POST   /api/reviews/                                 → run a review
  GET    /api/reviews/{id}/                            → retrieve a review
  POST   /api/reviews/{id}/findings/{fid}/feedback/   → accept / dismiss
"""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Review, ReviewFinding, ReviewUsage, LLMCallUsage
from .serializers import (
    ReviewSerializer,
    ReviewCreateSerializer,
    ReviewFindingSerializer,
    FeedbackSerializer,
)
from sentinel.services.review_orchestrator import ReviewOrchestrator
from sentinel.schemas.findings import Finding

logger = logging.getLogger(__name__)


class ReviewListCreateView(APIView):
    """POST /api/reviews/ — Trigger a new code review."""

    def post(self, request):
        # 1. Validate request
        create_serializer = ReviewCreateSerializer(data=request.data)
        if not create_serializer.is_valid():
            return Response(
                {"errors": create_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated = create_serializer.validated_data
        repo_path: str = validated["repo_path"]
        base_ref: str = validated["base_ref"]
        target_ref: str = validated["target_ref"]
        llm_provider: str = validated["llm_provider"]

        # 2. Create Review record in "running" state
        review = Review.objects.create(
            repo_path=repo_path,
            base_ref=base_ref,
            target_ref=target_ref,
            status=Review.Status.RUNNING,
        )

        logger.info("[%s] Review created — %s %s..%s", review.id, repo_path, base_ref, target_ref)

        # 3. Run the LangGraph orchestration (synchronous call wrapping async)
        orchestrator = ReviewOrchestrator()
        try:
            findings, errors, metadata, llm_usages = orchestrator.run_review_sync(
                review_id=str(review.id),
                repo_path=repo_path,
                base_ref=base_ref,
                target_ref=target_ref,
                llm_provider=llm_provider,
            )

            # 4. Persist findings
            db_findings = []
            for finding in findings:
                db_finding = ReviewFinding.objects.create(
                    review=review,
                    file=finding.file,
                    line=finding.line,
                    title=finding.title,
                    category=finding.category.value,
                    subcategory=finding.subcategory or "",
                    severity=finding.severity.value,
                    confidence=finding.confidence,
                    explanation=finding.explanation,
                    evidence=finding.evidence,
                    suggested_fix=finding.suggested_fix,
                    source=finding.source.value,
                    reviewer=finding.reviewer or "",
                )
                db_findings.append(db_finding)

            # 5. Persist usage
            total_input = 0
            total_output = 0
            total_tokens = 0
            total_latency = 0
            total_cost = 0.0
            models_used = set()
            calls = len(llm_usages)

            for u in llm_usages:
                cost = u.get("estimated_cost")
                if cost is not None:
                    total_cost += cost
                    
                LLMCallUsage.objects.create(
                    review=review,
                    reviewer=u.get("reviewer", "unknown"),
                    provider=u.get("provider", "unknown"),
                    model=u.get("model", "unknown"),
                    input_tokens=u.get("input_tokens", 0),
                    output_tokens=u.get("output_tokens", 0),
                    total_tokens=u.get("total_tokens", 0),
                    latency_ms=u.get("latency_ms", 0),
                    estimated_cost=cost,
                    status=u.get("status", "success"),
                )
                
                total_input += u.get("input_tokens", 0)
                total_output += u.get("output_tokens", 0)
                total_tokens += u.get("total_tokens", 0)
                models_used.add(u.get("model", "unknown"))
            
            # Review latency should ideally be the total duration of the review, 
            # not the sum of parallel reviewers.
            review_latency_ms = int(metadata.get("total_duration_seconds", 0) * 1000)

            ReviewUsage.objects.create(
                review=review,
                provider=llm_provider,
                total_input_tokens=total_input,
                total_output_tokens=total_output,
                total_tokens=total_tokens,
                total_latency_ms=review_latency_ms,
                total_estimated_cost=total_cost if any(u.get("estimated_cost") is not None for u in llm_usages) else None,
                llm_calls=calls,
                models_used=list(models_used),
            )

            # 6. Update review to completed
            review.status = Review.Status.COMPLETED
            review.errors = errors
            review.review_metadata = metadata
            review.raw_diff = metadata.get("raw_diff", "")
            review.save()

            logger.info("[%s] Review completed — %d findings", review.id, len(db_findings))

        except Exception as exc:
            logger.exception("[%s] Review orchestration failed: %s", review.id, exc)
            review.status = Review.Status.FAILED
            review.errors = [str(exc)]
            review.save()

        # 7. Return full serialized review
        serializer = ReviewSerializer(review)
        response_status = (
            status.HTTP_200_OK
            if review.status == Review.Status.COMPLETED
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        return Response(serializer.data, status=response_status)


class ReviewDetailView(APIView):
    """GET /api/reviews/{pk}/ — Retrieve a review with its findings."""

    def get(self, request, pk):
        try:
            review = Review.objects.prefetch_related("findings").get(pk=pk)
        except Review.DoesNotExist:
            return Response(
                {"error": "Review not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ReviewSerializer(review)
        return Response(serializer.data)


class FindingFeedbackView(APIView):
    """POST /api/reviews/{review_pk}/findings/{finding_pk}/feedback/
    
    Records user accept/dismiss decision for a finding.
    This feedback is persisted and is available as labelled evaluation data.
    """

    def post(self, request, review_pk, finding_pk):
        serializer = FeedbackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            finding = ReviewFinding.objects.get(
                pk=finding_pk, review_id=review_pk
            )
        except ReviewFinding.DoesNotExist:
            return Response(
                {"error": "Finding not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        finding.feedback = serializer.validated_data["action"]
        finding.save(update_fields=["feedback"])

        logger.info(
            "[%s] Finding %s feedback: %s", review_pk, finding_pk, finding.feedback
        )

        return Response(ReviewFindingSerializer(finding).data)
