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
from django.views import View

import threading
import json
from django.http import StreamingHttpResponse
from django.db import close_old_connections
from sentinel.services.events import publish_event, get_event_queue


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



def _run_and_save_review(review_id, repo_path, base_ref, target_ref, llm_provider):
    try:
        from .models import Review, ReviewFinding, LLMCallUsage, ReviewUsage
        review = Review.objects.get(id=review_id)
        
        orchestrator = ReviewOrchestrator()
        findings, errors, metadata, llm_usages = orchestrator.run_review_sync(
            review_id=str(review.id),
            repo_path=repo_path,
            base_ref=base_ref,
            target_ref=target_ref,
            llm_provider=llm_provider,
        )

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

        total_input, total_output, total_tokens, total_cost = 0, 0, 0, 0.0
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

        review_latency_ms = int(metadata.get("total_duration_seconds", 0) * 1000)

        ReviewUsage.objects.create(
            review=review,
            provider=llm_provider,
            llm_calls=calls,
            mcp_calls=metadata.get("mcp_calls", 0),
            unique_mcp_calls=metadata.get("unique_mcp_calls", 0),
            duplicate_mcp_calls=metadata.get("duplicate_mcp_calls", 0),
            agent_iterations=metadata.get("agent_iterations", 0),
            langgraph_node_executions=metadata.get("langgraph_node_executions", 0),
            retry_count=metadata.get("retry_count", 0),
            fallback_count=metadata.get("fallback_count", 0),
            timeout_count=metadata.get("timeout_count", 0),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_tokens,
            total_latency_ms=review_latency_ms,
            llm_latency_ms=metadata.get("llm_latency_ms", 0),
            mcp_latency_ms=metadata.get("mcp_latency_ms", 0),
            critical_path_latency_ms=metadata.get("critical_path_latency_ms", 0),
            total_estimated_cost=total_cost if any(u.get("estimated_cost") is not None for u in llm_usages) else None,
            models_used=list(models_used),
            finalization_reason=metadata.get("finalization_reason", "normal")
        )

        review.status = Review.Status.COMPLETED
        review.errors = errors
        review.review_metadata = metadata
        review.raw_diff = metadata.get("raw_diff", "")
        review.save()
        logger.info("[%s] Review completed — %d findings", review.id, len(db_findings))

    except Exception as exc:
        logger.exception("[%s] Review orchestration failed: %s", review_id, exc)
        from .models import Review
        try:
            r = Review.objects.get(id=review_id)
            r.status = Review.Status.FAILED
            r.errors = [str(exc)]
            r.save()
        except:
            pass
    finally:
        publish_event(str(review_id), {"type": "EOF"})
        close_old_connections()


class ReviewListCreateView(APIView):
    """POST /api/reviews/ — Trigger a new code review."""

    def post(self, request):
        # 1. Validate request
        create_serializer = ReviewCreateSerializer(data=request.data)
        if not create_serializer.is_valid():
            logger.warning("Bad Request Errors: %s", create_serializer.errors)
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

        if request.GET.get("stream") == "true":
            threading.Thread(target=_run_and_save_review, args=(review.id, repo_path, base_ref, target_ref, llm_provider)).start()
            logger.warning("Bad Request Errors: %s", create_serializer.errors)
            return Response({"id": review.id, "status": "running"}, status=status.HTTP_202_ACCEPTED)

        # Synchronous execution
        _run_and_save_review(review.id, repo_path, base_ref, target_ref, llm_provider)
        
        review.refresh_from_db()
        serializer = ReviewSerializer(review)
        response_status = status.HTTP_200_OK if review.status == Review.Status.COMPLETED else status.HTTP_500_INTERNAL_SERVER_ERROR
        return Response(serializer.data, status=response_status)



class ReviewDetailView(APIView):
    """GET /api/reviews/{pk}/ — Retrieve a review with its findings."""

    def get(self, request, pk):
        try:
            review = Review.objects.prefetch_related("findings").get(pk=pk)
        except Review.DoesNotExist:
            logger.warning("Bad Request Errors: %s", create_serializer.errors)
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
            logger.warning("Bad Request Errors: %s", create_serializer.errors)
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            finding = ReviewFinding.objects.get(
                pk=finding_pk, review_id=review_pk
            )
        except ReviewFinding.DoesNotExist:
            logger.warning("Bad Request Errors: %s", create_serializer.errors)
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

class ReviewStreamView(View):
    """GET /api/reviews/{review_id}/events/ — Stream SSE events for a review."""

    def get(self, request, review_id):
        def event_stream():
            q = get_event_queue(str(review_id))
            while True:
                event = q.get()
                if event.get("type") == "EOF":
                    yield f"data: {json.dumps(event)}\n\n"
                    break
                yield f"data: {json.dumps(event)}\n\n"
        
        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        return response
