import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { reviewsApi } from "../../api/client";
import { GitBranch, Plus, ArrowUpRight } from "lucide-react";
import type { Review } from "../../types";
import { formatDistanceToNow } from "../../utils/time";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";

const SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const;

const SEV_PILL: Record<string, string> = {
  CRITICAL: "bg-red-50 text-red-700 border-red-200",
  HIGH:     "bg-orange-50 text-orange-700 border-orange-200",
  MEDIUM:   "bg-amber-50 text-amber-700 border-amber-200",
  LOW:      "bg-blue-50 text-blue-700 border-blue-200",
};

function ReviewRow({ r }: { r: Review }) {
  const counts = SEVERITY_ORDER.reduce((acc, s) => {
    const n = r.findings.filter((f) => f.severity === s).length;
    if (n > 0) acc[s] = n;
    return acc;
  }, {} as Record<string, number>);

  const statusBg =
    r.status === "completed" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
    r.status === "failed"    ? "bg-red-50 text-red-700 border-red-200" :
                               "bg-blue-50 text-blue-700 border-blue-200";

  return (
    <li>
      <Link
        to={`/review/${r.id}`}
        className="group flex items-center gap-5 px-6 py-4 hover:bg-slate-50 transition-colors"
      >
        {/* Repo icon */}
        <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center flex-shrink-0">
          <GitBranch size={16} className="text-slate-500" />
        </div>

        {/* Repo + refs */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-800 truncate group-hover:text-[#6d5dfb] transition-colors">
            {r.repo_path.split("/").pop()}
          </p>
          <p className="text-xs text-slate-400 font-mono mt-0.5 truncate">
            <span className="text-blue-500">{r.base_ref}</span>
            {" → "}
            <span className="text-emerald-500">{r.target_ref}</span>
          </p>
        </div>

        {/* Severity breakdown */}
        <div className="hidden md:flex items-center gap-1.5 flex-shrink-0">
          {Object.entries(counts).length > 0
            ? Object.entries(counts).map(([s, n]) => (
                <span
                  key={s}
                  className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full border ${SEV_PILL[s] ?? ""}`}
                >
                  {n} {s[0] + s.slice(1).toLowerCase()}
                </span>
              ))
            : <span className="text-xs text-slate-400">—</span>
          }
        </div>

        {/* Status + time + arrow */}
        <div className="flex items-center gap-4 flex-shrink-0">
          <div className="text-right">
            <span className={`inline-block text-[10px] font-bold px-2 py-0.5 rounded-full border uppercase tracking-wide ${statusBg}`}>
              {r.status}
            </span>
            <p className="text-[11px] text-slate-400 mt-1">{formatDistanceToNow(r.created_at)}</p>
          </div>
          <ArrowUpRight size={15} className="text-slate-300 group-hover:text-[#6d5dfb] transition-colors" />
        </div>
      </Link>
    </li>
  );
}

export function ReviewsListPage() {
  const { data: reviews = [], isLoading, error, refetch } = useQuery({
    queryKey: ["reviews-list"],
    queryFn: reviewsApi.listReviews,
    staleTime: 10_000,
  });

  return (
    <div className="space-y-10 md:space-y-12">
      {/* ── Page header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between pb-6 border-b border-slate-200/80">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Reviews</h1>
          <p className="text-[15px] text-slate-500 mt-2">All code reviews, most recent first.</p>
        </div>
        <Link to="/new" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 text-[14px] font-medium rounded-lg text-white bg-gradient-to-b from-indigo-500 to-indigo-600 border border-indigo-700 shadow-md hover:from-indigo-600 hover:to-indigo-700 active:from-indigo-700 active:to-indigo-700 transition-all outline-none">
          <Plus size={16} />
          New review
        </Link>
      </div>

      {/* ── Table-style list card ────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">

        {/* Table header */}
        <div className="hidden md:grid grid-cols-[1fr_auto_auto] items-center gap-5 px-6 py-3 bg-slate-50 border-b border-slate-200">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Repository / refs</p>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Findings</p>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider text-right">Status</p>
        </div>

        {isLoading ? (
          <div className="divide-y divide-slate-100">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="px-6 py-4 flex items-center gap-5">
                <div className="skeleton w-10 h-10 rounded-xl flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="skeleton h-3.5 w-48 rounded" />
                  <div className="skeleton h-3 w-32 rounded" />
                </div>
                <div className="skeleton h-5 w-20 rounded-full" />
              </div>
            ))}
          </div>
        ) : error ? (
          <ErrorState message="Could not load reviews." onRetry={() => refetch()} />
        ) : reviews.length === 0 ? (
          <EmptyState
            type="no-reviews"
            action={
              <Link to="/new" className="inline-flex items-center justify-center gap-2 px-4 py-2 text-[13px] font-medium rounded-lg text-white bg-gradient-to-b from-indigo-500 to-indigo-600 border border-indigo-700 shadow-sm hover:from-indigo-600 hover:to-indigo-700 active:from-indigo-700 active:to-indigo-700 transition-all outline-none">
                <Plus size={14} />
                New review
              </Link>
            }
          />
        ) : (
          <ul
            className="divide-y divide-slate-100"
            aria-label={`${reviews.length} reviews`}
          >
            {reviews.map((r: Review) => (
              <ReviewRow key={r.id} r={r} />
            ))}
          </ul>
        )}
      </div>

      {/* Record count */}
      {!isLoading && !error && reviews.length > 0 && (
        <p className="text-xs text-slate-400 text-center">
          Showing {reviews.length} review{reviews.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
