import re
with open("frontend/src/features/reviews/ReviewResultsPage.tsx", "r") as f:
    content = f.read()

replacement = """
  const { data: review, isLoading, error, refetch } = useQuery({
    queryKey: ["review", id],
    queryFn: () => reviewsApi.getReview(id!),
    enabled: !!id,
    refetchInterval: (query) => 
      query.state.data?.status === "running" ? 2000 : false,
  });
"""

# The original has:
#   const { data: review, isLoading, error, refetch } = useQuery({
#     queryKey: ["review", id],
#     queryFn: () => reviewsApi.getReview(id!),
#     enabled: !!id,
#   });

pattern = r'const \{ data: review, isLoading, error, refetch \} = useQuery\(\{\s*queryKey: \["review", id\],\s*queryFn: \(\) => reviewsApi\.getReview\(id!\),\s*enabled: !!id,\s*\}\);'

content = re.sub(pattern, replacement.strip(), content)

with open("frontend/src/features/reviews/ReviewResultsPage.tsx", "w") as f:
    f.write(content)
