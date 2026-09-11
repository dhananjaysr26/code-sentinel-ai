"""Root URL configuration for CodeSentinel AI."""
from django.urls import path, include
from apps.reviews.overview_views import OverviewView, OverviewResetView

urlpatterns = [
    path("api/reviews/", include("apps.reviews.urls")),
    path("api/overview/", OverviewView.as_view(), name="overview"),
    path("api/overview/reset/", OverviewResetView.as_view(), name="overview-reset"),
]
