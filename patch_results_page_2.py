import re
with open("frontend/src/features/reviews/ReviewResultsPage.tsx", "r") as f:
    content = f.read()

content = content.replace("<ReviewerPipeline isRunning={false} />", '<ReviewerPipeline isRunning={review.status === "running"} />')

with open("frontend/src/features/reviews/ReviewResultsPage.tsx", "w") as f:
    f.write(content)
