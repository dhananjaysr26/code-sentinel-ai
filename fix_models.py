import re

with open("backend/apps/reviews/models.py", "r") as f:
    content = f.read()

new_fields = """    status = models.CharField(max_length=32, default="success")
    phase = models.CharField(max_length=64, blank=True)
    message_count = models.IntegerField(default=0)
    source_code_tokens = models.IntegerField(default=0)
    diff_tokens = models.IntegerField(default=0)
    system_prompt_tokens = models.IntegerField(default=0)
    reviewer_prompt_tokens = models.IntegerField(default=0)
    tool_schema_tokens = models.IntegerField(default=0)
    history_tokens = models.IntegerField(default=0)
    tool_result_tokens = models.IntegerField(default=0)
    structured_schema_tokens = models.IntegerField(default=0)"""

content = content.replace('    status = models.CharField(max_length=32, default="success")', new_fields)

with open("backend/apps/reviews/models.py", "w") as f:
    f.write(content)
