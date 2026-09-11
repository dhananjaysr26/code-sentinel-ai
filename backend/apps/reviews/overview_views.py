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

from apps.reviews.models import Review, ReviewFinding
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
        from django.db.models import Count
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

        # Evaluation quality — computed from seeded findings feedback
        # Seeded findings are those where source = "seeded" (or similar);
        # fall back to a simple accept/total proxy if no seeded data exists.
        seeded = ReviewFinding.objects.filter(source="seeded")
        seeded_total = seeded.count()
        seeded_detected = seeded.filter(feedback="accept").count()

        # Calculate precision / recall / f1 from feedback
        # Precision: accepted / (accepted + dismissed)
        # Recall: accepted / total_findings (proxy)
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
