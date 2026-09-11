"""Root URL configuration for CodeSentinel AI."""
from django.urls import path, include

urlpatterns = [
    path("api/reviews/", include("apps.reviews.urls")),
]
