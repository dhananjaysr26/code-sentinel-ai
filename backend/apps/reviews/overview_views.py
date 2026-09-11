"""
Overview views for CodeSentinel AI.

Endpoints:
  GET  /api/overview/         → aggregate stats
  POST /api/overview/reset/   → delete all reviews + findings
  GET  /api/reviews/list/     → paginated list of reviews (newest first)
"""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Count, Avg, Sum
from apps.reviews.models import Review, ReviewFinding, ReviewUsage
from apps.reviews.serializers import ReviewSerializer

logger = logging.getLogger(__name__)


class OverviewView(APIView):
    """GET /api/overview/ — Returns aggregate statistics."""

    def get(self, request):
        total_reviews = Review.objects.count()
        total_findings = ReviewFinding.objects.count()

        accepted = ReviewFinding.objects.filter(feedback="accept").count()
        dismissed = ReviewFinding.objects.filter(feedback="dismiss").count()
        unreviewed = ReviewFinding.objects.filter(feedback="none").count()

        reviewed = accepted + dismissed
        acceptance_rate = round((accepted / reviewed * 100), 1) if reviewed > 0 else 0.0

        # Severity distribution
        severity_qs = (
            ReviewFinding.objects
            .values("severity")
            .annotate(count=Count("id"))
        )
        severity_dist = {row["severity"]: row["count"] for row in severity_qs}

        # Reviewer distribution
        reviewer_qs = (
            ReviewFinding.objects
            .values("reviewer")
            .annotate(count=Count("id"))
        )
        reviewer_dist = {
            (row["reviewer"] or "unknown"): row["count"]
            for row in reviewer_qs
        }
        
        # Usage metrics
        usage_stats = ReviewUsage.objects.aggregate(
            avg_tokens=Avg("total_tokens"),
            avg_latency=Avg("total_latency_ms"),
            avg_cost=Avg("total_estimated_cost"),
            total_calls=Sum("llm_calls"),
        )
        
        avg_tokens = round(usage_stats["avg_tokens"]) if usage_stats["avg_tokens"] else 0
        avg_latency_ms = usage_stats["avg_latency"] if usage_stats["avg_latency"] else 0
        avg_latency_s = round(avg_latency_ms / 1000.0, 1)
        avg_cost = round(usage_stats["avg_cost"], 4) if usage_stats["avg_cost"] else None
        total_calls = usage_stats["total_calls"] or 0

        # Evaluation quality — computed from seeded findings feedback
        seeded = ReviewFinding.objects.filter(source="seeded")
        seeded_total = seeded.count()
        seeded_detected = seeded.filter(feedback="accept").count()

        precision = round((accepted / (accepted + dismissed) * 100), 1) if (accepted + dismissed) > 0 else 0.0
        recall = round((accepted / total_findings * 100), 1) if total_findings > 0 else 0.0
        f1 = round(
            (2 * precision * recall / (precision + recall)), 1
        ) if (precision + recall) > 0 else 0.0

        return Response(
            {
                "total_reviews": total_reviews,
                "total_findings": total_findings,
                "accepted": accepted,
                "dismissed": dismissed,
                "unreviewed": unreviewed,
                "acceptance_rate": acceptance_rate,
                "severity_distribution": severity_dist,
                "reviewer_distribution": reviewer_dist,
                "usage_metrics": {
                    "avg_tokens": avg_tokens,
                    "avg_latency_s": avg_latency_s,
                    "avg_cost": avg_cost,
                    "total_calls": total_calls,
                },
                "evaluation": {
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "seeded_total": seeded_total,
                    "seeded_detected": seeded_detected,
                },
            }
        )


class OverviewResetView(APIView):
    """POST /api/overview/reset/ — Delete all reviews and findings."""

    def post(self, request):
        deleted_findings, _ = ReviewFinding.objects.all().delete()
        deleted_reviews, _ = Review.objects.all().delete()
        logger.info(
            "Overview reset: deleted %d reviews and %d findings",
            deleted_reviews,
            deleted_findings,
        )
        return Response(
            {
                "deleted_reviews": deleted_reviews,
                "deleted_findings": deleted_findings,
            },
            status=status.HTTP_200_OK,
        )


class ReviewListView(APIView):
    """GET /api/reviews/list/ — Paginated list of recent reviews."""

    def get(self, request):
        reviews = Review.objects.prefetch_related("findings").order_by("-created_at")[:50]
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)
