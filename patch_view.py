with open("backend/apps/reviews/views.py", "r") as f:
    content = f.read()

# Add import if not exists
if "from django.views import View" not in content:
    content = content.replace("from rest_framework.views import APIView", "from rest_framework.views import APIView\nfrom django.views import View")

# Change base class
content = content.replace("class ReviewStreamView(APIView):", "class ReviewStreamView(View):")

with open("backend/apps/reviews/views.py", "w") as f:
    f.write(content)
