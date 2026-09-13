import re
with open("frontend/src/features/reviews/ReviewResultsPage.tsx", "r") as f:
    content = f.read()

# Replace import { useState }
content = content.replace('import { useState }', 'import { useState, useEffect }')

# In ReviewResultsPage component
old_hook = """  const { data: review, isLoading, error, refetch } = useQuery({
    queryKey: ["review", id],
    queryFn: () => reviewsApi.getReview(id!),
    enabled: !!id,
    refetchInterval: (query) => 
      query.state.data?.status === "running" ? 2000 : false,
  });"""

new_hook = """  const { data: review, isLoading, error, refetch } = useQuery({
    queryKey: ["review", id],
    queryFn: () => reviewsApi.getReview(id!),
    enabled: !!id,
    refetchInterval: (query) => 
      query.state.data?.status === "running" ? 2000 : false,
  });

  const [liveLogs, setLiveLogs] = useState<any[]>([]);
  useEffect(() => {
    if (review?.status === "running") {
      const cleanup = reviewsApi.listenToReviewEvents(id!, (event) => {
        setLiveLogs(prev => [...prev, event]);
      });
      return cleanup;
    }
  }, [review?.status, id]);
"""

content = content.replace(old_hook, new_hook)

# Now inject the live logs UI when it is running.
old_empty = """          <AnimatePresence mode="wait">
            {filtered.length === 0 ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="bg-white rounded-xl border border-slate-200 shadow-sm"
              >
                <EmptyState
                  type="no-findings"
                  description={
                    activeFilter !== "ALL"
                      ? `No ${activeFilter.toLowerCase()} severity findings.`
                      : undefined
                  }
                  action={
                    activeFilter !== "ALL" ? (
                      <button
                        onClick={() => setActiveFilter("ALL")}
                        className="text-sm text-[#6d5dfb] hover:underline font-medium"
                      >
                        Clear filter
                      </button>
                    ) : undefined
                  }
                />
              </motion.div>
            ) : ("""

new_empty = """          <AnimatePresence mode="wait">
            {review.status === "running" ? (
              <motion.div
                key="running"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4"
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-4 h-4 border-2 border-[#6d5dfb] border-t-transparent rounded-full animate-spin"></div>
                  <h3 className="text-sm font-semibold text-slate-800">Review in progress...</h3>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 h-64 overflow-y-auto font-mono text-[11px] text-slate-600 space-y-1 flex flex-col-reverse">
                  {liveLogs.length === 0 && <div className="text-slate-400 italic">Starting agents...</div>}
                  {liveLogs.slice().reverse().map((log, i) => (
                    <div key={i} className="flex gap-3">
                      <span className="text-slate-400 shrink-0">{new Date(log.timestamp || Date.now()).toLocaleTimeString()}</span>
                      <span className="font-semibold text-slate-700 w-24 shrink-0 truncate uppercase">{log.reviewer || log.node}</span>
                      <span className="text-[#6d5dfb] truncate">{log.event}:</span>
                      <span className="text-slate-700 truncate">{log.details}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ) : filtered.length === 0 ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="bg-white rounded-xl border border-slate-200 shadow-sm"
              >
                <EmptyState
                  type="no-findings"
                  description={
                    activeFilter !== "ALL"
                      ? `No ${activeFilter.toLowerCase()} severity findings.`
                      : undefined
                  }
                  action={
                    activeFilter !== "ALL" ? (
                      <button
                        onClick={() => setActiveFilter("ALL")}
                        className="text-sm text-[#6d5dfb] hover:underline font-medium"
                      >
                        Clear filter
                      </button>
                    ) : undefined
                  }
                />
              </motion.div>
            ) : ("""

content = content.replace(old_empty, new_empty)

with open("frontend/src/features/reviews/ReviewResultsPage.tsx", "w") as f:
    f.write(content)
