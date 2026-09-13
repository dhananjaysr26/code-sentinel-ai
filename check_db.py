import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sentinel.settings")
django.setup()

from apps.reviews.models import Review
for r in Review.objects.all():
    print(r.id, r.status)
