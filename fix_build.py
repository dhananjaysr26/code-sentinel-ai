with open("frontend/src/features/reviews/ReviewResultsPage.tsx", "r") as f:
    content = f.read()

content = content.replace("review.usage?.total_estimated_cost.toFixed", "review.usage?.total_estimated_cost?.toFixed")

with open("frontend/src/features/reviews/ReviewResultsPage.tsx", "w") as f:
    f.write(content)
