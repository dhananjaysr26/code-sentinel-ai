import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { reviewsApi } from "../../api/client";
import { FindingCard } from "../../components/FindingCard";
import { SeverityBadge } from "../../components/SeverityBadge";
import { ReviewerPipeline } from "../../components/ReviewerPipeline";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import type { Severity, Finding } from "../../types";
import {
  ArrowLeft, GitCommit, CheckCircle2,
  XCircle, Clock, SlidersHorizontal,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const SEVERITY_ORDER: Severity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

// ─────────────────────────────────────────────────────────────────────────────
// Loading skeleton
// ─────────────────────────────────────────────────────────────────────────────
function PageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="skeleton h-4 w-28 rounded" />
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <div className="skeleton h-5 w-48 mb-3 rounded" />
        <div className="skeleton h-3 w-36 rounded" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <div className="skeleton h-48 rounded-xl" />
          <div className="skeleton h-36 rounded-xl" />
        </div>
        <div className="lg:col-span-3 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <div className="skeleton h-4 w-24 mb-3 rounded" />
              <div className="skeleton h-5 w-3/4 mb-2 rounded" />
              <div className="skeleton h-3 w-44 mb-4 rounded" />
              <div className="skeleton h-14 rounded-lg" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Filter sidebar button
// ─────────────────────────────────────────────────────────────────────────────
const SEV_DOT: Record<Severity, string> = {
  CRITICAL: "bg-red-500",
  HIGH:     "bg-orange-400",
  MEDIUM:   "bg-amber-400",
  LOW:      "bg-blue-400",
};

function FilterButton({
  active, onClick, label, count,
  dot,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
  dot?: string;
}) {
  return (
    <button
      role="option"
      aria-selected={active}
      onClick={onClick}
      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm transition-all ${
        active
          ? "bg-[#6d5dfb]/8 text-[#6d5dfb] font-semibold"
          : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
      }`}
    >
      <span className="flex items-center gap-2.5">
        {dot && (
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dot} ${active ? "opacity-100" : "opacity-60"}`} />
        )}
        {label}
      </span>
      <span className={`font-mono text-xs ${active ? "text-[#6d5dfb]" : "text-slate-400"}`}>
        {count}
      </span>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────
export function ReviewResultsPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [activeFilter, setActiveFilter] = useState<Severity | "ALL">("ALL");

  const { data: review, isLoading, error, refetch } = useQuery({
    queryKey: ["review", id],
    queryFn: () => reviewsApi.getReview(id!),
    enabled: !!id,
  });

  const feedbackMutation = useMutation({
    mutationFn: ({ findingId, action }: { findingId: string; action: "accept" | "dismiss" }) =>
      reviewsApi.submitFeedback(id!, findingId, { action }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review", id] });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  if (isLoading) return <PageSkeleton />;

  if (error || !review) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <ErrorState
          title="Review not found"
          message="This review may have been deleted or does not exist."
          onRetry={() => refetch()}
        />
        <div className="pb-6 text-center">
          <Link to="/reviews" className="text-sm text-[#6d5dfb] hover:underline font-medium">
            ← Back to reviews
          </Link>
        </div>
      </div>
    );
  }

  const counts = SEVERITY_ORDER.reduce(
    (acc, s) => ({ ...acc, [s]: review.findings.filter((f) => f.severity === s).length }),
    {} as Record<Severity, number>
  );

  const filtered: Finding[] =
    activeFilter === "ALL"
      ? review.findings
      : review.findings.filter((f) => f.severity === activeFilter);

  const StatusIcon  = review.status === "completed" ? CheckCircle2 : review.status === "failed" ? XCircle : Clock;
  const statusBg    = review.status === "completed" ? "bg-emerald-50 border-emerald-200 text-emerald-700" : review.status === "failed" ? "bg-red-50 border-red-200 text-red-700" : "bg-blue-50 border-blue-200 text-blue-700";
  const repoName    = review.repo_path.split("/").pop() ?? review.repo_path;

  return (
    <div className="space-y-8 md:space-y-10">

      {/* ── Back link ──────────────────────────────────────────────── */}
      <Link
        to="/reviews"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 transition-colors font-medium mb-2"
      >
        <ArrowLeft size={14} />
        Back to reviews
      </Link>

      {/* ── Review header card ──────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-5">

          {/* Left: status + title + refs */}
          <div className="space-y-2">
            <span className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full border uppercase tracking-wide ${statusBg}`}>
              <StatusIcon size={11} />
              {review.status}
            </span>
            <h1 className="text-xl font-bold text-slate-900">{repoName}</h1>
            <div className="flex items-center gap-1.5 text-sm font-mono text-slate-500">
              <GitCommit size={13} className="text-slate-400" />
              <span className="text-blue-600 font-semibold">{review.base_ref}</span>
              <span className="text-slate-400">→</span>
              <span className="text-emerald-600 font-semibold">{review.target_ref}</span>
            </div>
          </div>

          {/* Right: severity chips */}
          <div className="flex flex-wrap items-center gap-2 sm:justify-end">
            <span className="text-sm font-semibold text-slate-500">
              {review.findings.length} {review.findings.length === 1 ? "finding" : "findings"}
            </span>
            {SEVERITY_ORDER.filter((s) => counts[s] > 0).map((s) => (
              <div key={s} className="flex items-center gap-1">
                <SeverityBadge severity={s} showIcon size="sm" />
                <span className="text-xs font-mono font-semibold text-slate-500">×{counts[s]}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Two-column layout ───────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">

        {/* ── Sticky sidebar ──────────────────────────────────────── */}
        <aside className="lg:col-span-1 lg:sticky lg:top-[76px] space-y-4">

          {/* Filter */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
            <div className="flex items-center gap-2 mb-3 pb-3 border-b border-slate-100">
              <SlidersHorizontal size={13} className="text-slate-400" aria-hidden />
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Filter</p>
            </div>
            <ul role="listbox" aria-label="Filter by severity" className="space-y-0.5">
              <li>
                <FilterButton
                  active={activeFilter === "ALL"}
                  onClick={() => setActiveFilter("ALL")}
                  label="All findings"
                  count={review.findings.length}
                />
              </li>
              {SEVERITY_ORDER.map((s) => (
                <li key={s}>
                  <FilterButton
                    active={activeFilter === s}
                    onClick={() => setActiveFilter(s)}
                    label={s[0] + s.slice(1).toLowerCase()}
                    count={counts[s]}
                    dot={SEV_DOT[s]}
                  />
                </li>
              ))}
            </ul>
          </div>

          {/* Agent pipeline */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
            <ReviewerPipeline isRunning={false} />
          </div>

          {/* Review meta */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-4">
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Repository</p>
              <p className="text-xs text-slate-700 font-mono break-all leading-relaxed">{review.repo_path}</p>
            </div>
            <div className="border-t border-slate-100 pt-3">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Review ID</p>
              <p className="text-[11px] text-slate-500 font-mono break-all">{review.id}</p>
            </div>
          </div>
        </aside>

        {/* ── Findings list ────────────────────────────────────────── */}
        <div className="lg:col-span-3">
          <AnimatePresence mode="wait">
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
            ) : (
              <motion.div
                key={activeFilter}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-4"
              >
                {filtered.map((finding, i) => (
                  <motion.div
                    key={finding.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04, duration: 0.22 }}
                  >
                    <FindingCard
                      finding={finding}
                      onStatusChange={(findingId, action) =>
                        feedbackMutation.mutate({ findingId, action })
                      }
                    />
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
