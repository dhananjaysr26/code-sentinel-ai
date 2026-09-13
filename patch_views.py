import re
with open("backend/apps/reviews/views.py", "r") as f:
    content = f.read()

content = content.replace("            return Response(", '            logger.warning("Bad Request Errors: %s", create_serializer.errors)\n            return Response(')

with open("backend/apps/reviews/views.py", "w") as f:
    f.write(content)
