import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import type { CreateReviewRequest, Review } from "../types";
import { reviewsApi } from "../api/client";
import { Loader2, FolderGit2, GitBranch, GitMerge, ChevronRight } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { ReviewerPipeline } from "./ReviewerPipeline";

interface Props {
  onReviewComplete: (review: Review) => void;
}

const labelClass = "flex items-center gap-1.5 text-[11px] font-semibold text-slate-500 mb-1.5 uppercase tracking-wider";

const inputClass = [
  "w-full px-4 py-3 text-[13px] text-slate-900 bg-white placeholder-slate-400 font-mono",
  "border border-slate-200 rounded-[8px] shadow-sm",
  "focus:outline-none focus:border-[#6d5dfb] focus:ring-4 focus:ring-[#6d5dfb]/10",
  "transition-all duration-200",
  "disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed",
].join(" ");

export function ReviewForm({ onReviewComplete }: Props) {
  const [repoPath,    setRepoPath]    = useState("");
  const [baseRef,     setBaseRef]     = useState("HEAD~1");
  const [targetRef,   setTargetRef]   = useState("HEAD");
  const [llmProvider, setLlmProvider] = useState<"openai" | "bedrock">("bedrock");

  const mutation = useMutation({
    mutationFn: (req: CreateReviewRequest) => reviewsApi.createReview(req),
    onSuccess: (review) => onReviewComplete(review),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoPath.trim()) return;
    mutation.mutate({
      repo_path:    repoPath.trim(),
      base_ref:     baseRef.trim()   || "HEAD~1",
      target_ref:   targetRef.trim() || "HEAD",
      llm_provider: llmProvider,
    });
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">

      {/* ── Repository path ─────────────────────────────────────────── */}
      <div>
        <label htmlFor="repo-path" className={labelClass}>
          <FolderGit2 size={13} className="text-[#6d5dfb]" aria-hidden />
          Repository path
        </label>
        <input
          id="repo-path"
          type="text"
          value={repoPath}
          onChange={(e) => setRepoPath(e.target.value)}
          placeholder="/absolute/path/to/your/repo"
          required
          disabled={mutation.isPending}
          className={inputClass}
          aria-describedby="repo-path-hint"
        />
        <p id="repo-path-hint" className="mt-2 text-[12px] text-slate-400">
          Must be an absolute path to a local git repository on this machine.
        </p>
      </div>

      {/* ── Base / Target refs ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div>
          <label htmlFor="base-ref" className={labelClass}>
            <GitBranch size={13} className="text-blue-500" aria-hidden />
            Base ref
          </label>
          <input
            id="base-ref"
            type="text"
            value={baseRef}
            onChange={(e) => setBaseRef(e.target.value)}
            placeholder="HEAD~1"
            disabled={mutation.isPending}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="target-ref" className={labelClass}>
            <GitMerge size={13} className="text-emerald-500" aria-hidden />
            Target ref
          </label>
          <input
            id="target-ref"
            type="text"
            value={targetRef}
            onChange={(e) => setTargetRef(e.target.value)}
            placeholder="HEAD"
            disabled={mutation.isPending}
            className={inputClass}
          />
        </div>
      </div>

      {/* ── AI provider ─────────────────────────────────────────────── */}
      <div>
        <p className={labelClass}>AI provider</p>
        <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label="AI provider">
          {(["bedrock", "openai"] as const).map((p) => (
            <button
              key={p}
              type="button"
              role="radio"
              aria-checked={llmProvider === p}
              disabled={mutation.isPending}
              onClick={() => setLlmProvider(p)}
              className={[
                "px-4 py-3 rounded-[8px] text-[13px] font-semibold transition-all border outline-none",
                llmProvider === p
                  ? "bg-[#f0effe] border-[#6d5dfb]/40 text-[#5b4de8] shadow-[inset_0_0_0_1px_rgba(109,93,251,0.08)]"
                  : "bg-white border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700 hover:bg-slate-50 shadow-sm",
              ].join(" ")}
            >
              {p === "bedrock" ? "AWS Bedrock" : "OpenAI GPT-4o"}
            </button>
          ))}
        </div>
      </div>

      {/* ── Submit ──────────────────────────────────────────────────── */}
      <div className="pt-4">
        <button
          type="submit"
          disabled={mutation.isPending || !repoPath.trim()}
          className="w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-lg text-sm font-semibold text-white bg-gradient-to-b from-indigo-500 to-indigo-600 border border-indigo-700 shadow-md hover:from-indigo-600 hover:to-indigo-700 active:from-indigo-700 active:to-indigo-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
        >
          {mutation.isPending ? (
            <>
              <Loader2 className="animate-spin" size={16} />
              Analyzing changes…
            </>
          ) : (
            <>
              Run code review
              <ChevronRight size={16} />
            </>
          )}
        </button>
      </div>

      {/* ── Running pipeline inline ──────────────────────────────────── */}
      <AnimatePresence>
        {mutation.isPending && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="p-5 rounded-[10px] bg-slate-50 border border-slate-200 shadow-[inset_0_1px_2px_rgba(0,0,0,0.02)]"
          >
            <ReviewerPipeline isRunning />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Error ───────────────────────────────────────────────────── */}
      <AnimatePresence>
        {mutation.isError && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="p-4 rounded-[10px] bg-red-50 border border-red-200 shadow-sm"
            role="alert"
          >
            <p className="text-sm font-semibold text-red-700 mb-0.5">Review failed</p>
            <p className="text-xs text-red-600 leading-relaxed">
              {mutation.error instanceof Error
                ? mutation.error.message
                : "An unexpected error occurred. Please try again."}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </form>
  );
}
