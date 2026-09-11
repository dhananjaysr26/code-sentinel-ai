"""URL patterns for the reviews app."""
from django.urls import path
from . import views
from .overview_views import OverviewView, OverviewResetView, ReviewListView

urlpatterns = [
    # Reviews CRUD
    path("", views.ReviewListCreateView.as_view(), name="review-list-create"),
    path("<uuid:pk>/", views.ReviewDetailView.as_view(), name="review-detail"),
    path(
        "<uuid:review_pk>/findings/<uuid:finding_pk>/feedback/",
        views.FindingFeedbackView.as_view(),
        name="finding-feedback",
    ),
    # List (GET only)
    path("list/", ReviewListView.as_view(), name="review-list"),
]
