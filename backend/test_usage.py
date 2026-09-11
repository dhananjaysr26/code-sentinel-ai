import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.reviews.views import ReviewListCreateView
from rest_framework.test import APIRequestFactory

factory = APIRequestFactory()
request = factory.post('/api/reviews/', {
    'repo_path': '/Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/backend',
    'base_ref': 'HEAD~1',
    'target_ref': 'HEAD',
    'llm_provider': 'bedrock'
}, format='json')

view = ReviewListCreateView.as_view()
response = view(request)
print("Status:", response.status_code)
if response.status_code == 200:
    data = response.data
    print("Review ID:", data.get("id"))
    print("Usage:", data.get("usage"))
    print("Reviewer Usage:", len(data.get("reviewer_usage", [])))
    if data.get("reviewer_usage"):
        print("First reviewer usage:", data.get("reviewer_usage")[0])
else:
    print("Errors:", response.data)
