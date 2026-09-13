import re

with open("backend/apps/reviews/views.py", "r") as f:
    content = f.read()

imports = """
import threading
import json
from django.http import StreamingHttpResponse
from django.db import close_old_connections
from sentinel.services.events import publish_event, get_event_queue
"""

content = content.replace("from rest_framework.views import APIView", "from rest_framework.views import APIView\n" + imports)

run_func = """
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
"""

post_replacement = """        logger.info("[%s] Review created — %s %s..%s", review.id, repo_path, base_ref, target_ref)

        if request.GET.get("stream") == "true":
            threading.Thread(target=_run_and_save_review, args=(review.id, repo_path, base_ref, target_ref, llm_provider)).start()
            return Response({"id": review.id, "status": "running"}, status=status.HTTP_202_ACCEPTED)

        # Synchronous execution
        _run_and_save_review(review.id, repo_path, base_ref, target_ref, llm_provider)
        
        review.refresh_from_db()
        serializer = ReviewSerializer(review)
        response_status = status.HTTP_200_OK if review.status == Review.Status.COMPLETED else status.HTTP_500_INTERNAL_SERVER_ERROR
        return Response(serializer.data, status=response_status)
"""

# Extract the body of post and replace it
new_content = re.sub(
    r'        logger.info\("\[%s\] Review created — %s %s..%s", review.id, repo_path, base_ref, target_ref\)\n\n.*?        return Response\(serializer.data, status=response_status\)',
    post_replacement,
    content,
    flags=re.DOTALL
)

# Insert the helper function before the class
new_content = new_content.replace('class ReviewListCreateView(APIView):', run_func + '\n\nclass ReviewListCreateView(APIView):')

stream_view = """
class ReviewStreamView(APIView):
    \"\"\"GET /api/reviews/{review_id}/events/ — Stream SSE events for a review.\"\"\"

    def get(self, request, review_id):
        def event_stream():
            q = get_event_queue(str(review_id))
            while True:
                event = q.get()
                if event.get("type") == "EOF":
                    yield f"data: {json.dumps(event)}\\n\\n"
                    break
                yield f"data: {json.dumps(event)}\\n\\n"
        
        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        return response
"""

new_content = new_content + stream_view

with open("backend/apps/reviews/views.py", "w") as f:
    f.write(new_content)
