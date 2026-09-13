import re
with open("frontend/src/components/ReviewForm.tsx", "r") as f:
    content = f.read()

# Remove the inline pipeline
pattern = r'\{/\* ── Running pipeline inline ──────────────────────────────────── \*/\}.*?</AnimatePresence>'
content = re.sub(pattern, '', content, flags=re.DOTALL)

with open("frontend/src/components/ReviewForm.tsx", "w") as f:
    f.write(content)
