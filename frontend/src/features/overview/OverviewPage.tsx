import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";

import { overviewApi, reviewsApi } from "../../api/client";
import type { Review } from "../../types";
import { ResetConfirmationModal } from "../../components/ResetConfirmationModal";
import { toast } from "../../components/Toast";
import { formatDistanceToNow } from "../../utils/time";
import {
  GitBranch, CheckCircle2, XCircle, AlertCircle,
  BarChart3, Trash2, Users, FlaskConical, Code2,
} from "lucide-react";

// ─────────────────────────────────────────────────────────────────────────────
// Shared card wrapper
// ─────────────────────────────────────────────────────────────────────────────
function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-sm p-6 ${className}`}>
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Card section header with bottom border
// ─────────────────────────────────────────────────────────────────────────────
function SectionHead({
  icon: Icon,
  title,
  action,
}: {
  icon?: React.ElementType;
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="section-header">
      {Icon && <Icon size={15} className="text-slate-400 flex-shrink-0" aria-hidden />}
      <h3 className="text-sm font-semibold text-slate-700 flex-1">{title}</h3>
      {action && <div className="ml-auto">{action}</div>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Skeleton placeholders
// ─────────────────────────────────────────────────────────────────────────────
function MetricCardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-3">
      <div className="skeleton h-3 w-24 rounded" />
      <div className="skeleton h-9 w-20 rounded" />
      <div className="skeleton h-2.5 w-32 rounded" />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// KPI metric card
// ─────────────────────────────────────────────────────────────────────────────
function MetricCard({
  label, value, sub, icon: Icon, iconBg, iconColor,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className={`w-9 h-9 rounded-lg ${iconBg} flex items-center justify-center mb-4`}>
        <Icon size={16} className={iconColor} aria-hidden />
      </div>
      <p className="text-[28px] font-bold text-slate-900 leading-none tracking-tight mb-1.5">{value}</p>
      <p className="text-sm font-medium text-slate-500">{label}</p>
      {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Severity distribution bars
// ─────────────────────────────────────────────────────────────────────────────
const SEV_CONFIG = [
  { key: "CRITICAL", label: "Critical", bar: "bg-red-500",    pill: "bg-red-50 text-red-700 border border-red-200"    },
  { key: "HIGH",     label: "High",     bar: "bg-orange-400", pill: "bg-orange-50 text-orange-700 border border-orange-200" },
  { key: "MEDIUM",   label: "Medium",   bar: "bg-amber-400",  pill: "bg-amber-50 text-amber-700 border border-amber-200"   },
  { key: "LOW",      label: "Low",      bar: "bg-blue-400",   pill: "bg-blue-50 text-blue-700 border border-blue-200"      },
];

function FindingDistribution({ dist }: { dist: Record<string, number> }) {
  const total = Object.values(dist).reduce((a, b) => a + b, 0);
  return (
    <div className="space-y-4">
      {SEV_CONFIG.map(({ key, label, bar, pill }) => {
        const count = dist[key] ?? 0;
        const pct   = total > 0 ? Math.round((count / total) * 100) : 0;
        return (
          <div key={key}>
            <div className="flex items-center justify-between mb-2">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-md ${pill}`}>{label}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">{pct}%</span>
                <span className="text-sm font-semibold text-slate-700 w-7 text-right font-mono">{count}</span>
              </div>
            </div>
            <div
              className="h-2 bg-slate-100 rounded-full overflow-hidden"
              role="progressbar"
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${label} findings`}
            >
              <motion.div
                className={`h-full rounded-full ${bar}`}
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.7, ease: "easeOut" }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Reviewer distribution
// ─────────────────────────────────────────────────────────────────────────────
function ReviewerStats({ dist }: { dist: Record<string, number> }) {
  const entries = Object.entries(dist).sort((a, b) => b[1] - a[1]);
  const total   = entries.reduce((s, [, v]) => s + v, 0);

  if (entries.length === 0)
    return <p className="text-sm text-slate-400 py-4 text-center">No reviewer data yet.</p>;

  return (
    <div className="space-y-4">
      {entries.map(([reviewer, count]) => {
        const pct = total > 0 ? Math.round((count / total) * 100) : 0;
        return (
          <div key={reviewer}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-700 capitalize">{reviewer || "Unknown"}</span>
              <span className="text-sm font-semibold text-slate-700 font-mono">{count}</span>
            </div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-[#6d5dfb]"
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.7, ease: "easeOut" }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Evaluation quality
// ─────────────────────────────────────────────────────────────────────────────
function EvalQualityCard({ precision, recall, f1, seeded_total, seeded_detected }: {
  precision: number; recall: number; f1: number;
  seeded_total: number; seeded_detected: number;
}) {
  const metrics = [
    { label: "Precision", value: precision, desc: "Accepted / (Accepted + Dismissed)" },
    { label: "Recall",    value: recall,    desc: "Accepted / Total findings"          },
    { label: "F1 Score",  value: f1,        desc: "Harmonic mean of precision & recall" },
  ];

  return (
    <Card>
      <SectionHead
        icon={FlaskConical}
        title="Evaluation quality"
        action={
          <span className="text-xs text-slate-400 italic bg-slate-50 border border-slate-200 px-2.5 py-1 rounded-md">
            Not developer feedback
          </span>
        }
      />
      <div className="grid grid-cols-3 gap-4">
        {metrics.map(({ label, value, desc }) => (
          <div key={label} className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-center">
            <p className="text-2xl font-bold text-slate-900 mb-0.5">{value}%</p>
            <p className="text-xs font-semibold text-slate-600 mb-1">{label}</p>
            <p className="text-[10px] text-slate-400 leading-relaxed hidden lg:block">{desc}</p>
          </div>
        ))}
      </div>
      {seeded_total > 0 && (
        <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between">
          <span className="text-sm text-slate-500">Seeded defects detected</span>
          <span className="text-sm font-semibold text-slate-700 font-mono">
            {seeded_detected} / {seeded_total}
          </span>
        </div>
      )}
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Recent reviews list
// ─────────────────────────────────────────────────────────────────────────────
function RecentReviews() {
  const { data: reviews = [], isLoading } = useQuery({
    queryKey: ["reviews-list"],
    queryFn: reviewsApi.listReviews,
    staleTime: 10_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="skeleton h-[68px] rounded-lg" />
        ))}
      </div>
    );
  }

  if (reviews.length === 0) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm text-slate-400">No reviews yet.</p>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-slate-100" aria-label="Recent reviews">
      {(reviews as Review[]).slice(0, 8).map((r) => (
        <li key={r.id}>
          <Link
            to={`/review/${r.id}`}
            className="flex items-center gap-4 py-4 px-1 hover:bg-slate-50 rounded-lg transition-colors group"
          >
            {/* Icon */}
            <div className="w-9 h-9 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center flex-shrink-0">
              <GitBranch size={15} className="text-slate-500" />
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-800 truncate group-hover:text-[#6d5dfb] transition-colors">
                {r.repo_path.split("/").pop()}
              </p>
              <p className="text-xs text-slate-400 font-mono mt-0.5 truncate">
                {r.base_ref} → {r.target_ref}
              </p>
            </div>

            {/* Count */}
            <div className="hidden sm:block text-center flex-shrink-0">
              <p className="text-sm font-semibold text-slate-700">{r.findings.length}</p>
              <p className="text-[10px] text-slate-400">findings</p>
            </div>

            {/* Status */}
            <div className="flex-shrink-0 text-right">
              <span className={`inline-block text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide border ${
                r.status === "completed" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                r.status === "failed"    ? "bg-red-50 text-red-700 border-red-200" :
                                           "bg-blue-50 text-blue-700 border-blue-200"
              }`}>
                {r.status}
              </span>
              <p className="text-[10px] text-slate-400 mt-1">{formatDistanceToNow(r.created_at)}</p>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Overview page
// ─────────────────────────────────────────────────────────────────────────────
export function OverviewPage() {
  const qc = useQueryClient();
  const [showReset, setShowReset] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["overview"],
    queryFn: overviewApi.getOverview,
    staleTime: 10_000,
  });

  const resetMutation = useMutation({
    mutationFn: overviewApi.reset,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["overview"] });
      qc.invalidateQueries({ queryKey: ["reviews-list"] });
      setShowReset(false);
      toast("success", "Review data has been reset.");
    },
    onError: () => toast("error", "Reset failed. Please try again."),
  });

  return (
    <div className="space-y-10 md:space-y-12">

      {/* ── Page header ───────────────────────────────────────────── */}
      <div className="pb-6 border-b border-slate-200/80">
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Overview</h1>
        <p className="text-[15px] text-slate-500 mt-2">
          Track review activity, findings, developer feedback, and evaluation quality.
        </p>
      </div>

      {/* ── KPI cards ─────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-5">
          {[1, 2, 3, 4, 5].map((i) => <MetricCardSkeleton key={i} />)}
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700" role="alert">
          Failed to load overview data.{" "}
          <button onClick={() => refetch()} className="underline font-semibold">Retry</button>
        </div>
      ) : data ? (
        <>
          {/* Row 1: 5 KPI tiles */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-5">
            <MetricCard
              label="Total reviews"
              value={data.total_reviews}
              icon={GitBranch}
              iconBg="bg-violet-50"
              iconColor="text-[#6d5dfb]"
            />
            <MetricCard
              label="Total findings"
              value={data.total_findings}
              icon={BarChart3}
              iconBg="bg-slate-100"
              iconColor="text-slate-500"
            />
            <MetricCard
              label="Linter findings"
              value={data.linter_findings ?? 0}
              icon={Code2}
              iconBg="bg-blue-50"
              iconColor="text-blue-500"
            />
            <MetricCard
              label="Accepted"
              value={data.accepted}
              icon={CheckCircle2}
              iconBg="bg-emerald-50"
              iconColor="text-emerald-600"
            />
            <MetricCard
              label="Dismissed"
              value={data.dismissed}
              icon={XCircle}
              iconBg="bg-red-50"
              iconColor="text-red-500"
            />
          </div>

          {/* Row 2: Acceptance rate + Unreviewed */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Acceptance rate */}
            <Card>
              <div className="flex items-start justify-between mb-5">
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Acceptance rate
                  </p>
                  <p className="text-4xl font-bold text-slate-900 tracking-tight">
                    {data.acceptance_rate}%
                  </p>
                </div>
                <div className="w-9 h-9 rounded-lg bg-violet-50 flex items-center justify-center">
                  <AlertCircle size={16} className="text-[#6d5dfb]" aria-hidden />
                </div>
              </div>
              <div
                className="h-2.5 bg-slate-100 rounded-full overflow-hidden mb-3"
                role="progressbar"
                aria-valuenow={data.acceptance_rate}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Acceptance rate"
              >
                <motion.div
                  className="h-full rounded-full bg-[#6d5dfb]"
                  initial={{ width: 0 }}
                  animate={{ width: `${data.acceptance_rate}%` }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                />
              </div>
              <p className="text-xs text-slate-400">
                <span className="text-emerald-600 font-semibold">{data.accepted} accepted</span>
                {" · "}
                <span className="text-red-500 font-semibold">{data.dismissed} dismissed</span>
                {" · "}
                accepted / (accepted + dismissed)
              </p>
            </Card>

            {/* Unreviewed */}
            <Card>
              <div className="flex items-start justify-between mb-5">
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Unreviewed
                  </p>
                  <p className="text-4xl font-bold text-slate-900 tracking-tight">
                    {data.unreviewed}
                  </p>
                </div>
                <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center">
                  <AlertCircle size={16} className="text-amber-500" aria-hidden />
                </div>
              </div>
              <p className="text-xs text-slate-400">
                Findings pending developer feedback (accept or dismiss).
              </p>
            </Card>
          </div>

          {/* Row 3: AI Usage (Tokens, Latency, Cost, Calls) */}
          {data.usage_metrics && (
            <Card>
              <SectionHead icon={BarChart3} title="AI Usage" />
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-2">
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Avg tokens / rev</p>
                  <p className="text-xl font-bold text-slate-900 font-mono">{data.usage_metrics.avg_tokens.toLocaleString()}</p>
                </div>
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Avg latency / rev</p>
                  <p className="text-xl font-bold text-slate-900 font-mono">{data.usage_metrics.avg_latency_s.toFixed(1)}s</p>
                </div>
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Avg cost / rev</p>
                  <p className="text-xl font-bold text-slate-900 font-mono">
                    {data.usage_metrics.avg_cost !== null ? `$${data.usage_metrics.avg_cost.toFixed(4)}` : "N/A"}
                  </p>
                </div>
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Total LLM calls</p>
                  <p className="text-xl font-bold text-slate-900 font-mono">{data.usage_metrics.total_calls.toLocaleString()}</p>
                </div>
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Total MCP calls</p>
                  <p className="text-xl font-bold text-slate-900 font-mono">{data.usage_metrics.total_tool_calls.toLocaleString()}</p>
                </div>
              </div>
            </Card>
          )}

          {/* Row 4: Finding distribution + Reviewer stats */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Card>
              <SectionHead icon={BarChart3} title="Finding distribution" />
              <FindingDistribution dist={data.severity_distribution} />
            </Card>
            <Card>
              <SectionHead icon={Users} title="Findings by reviewer" />
              <ReviewerStats dist={data.reviewer_distribution} />
            </Card>
          </div>

          {/* Row 5: Evaluation quality */}
          <EvalQualityCard {...data.evaluation} />
        </>
      ) : null}

      {/* ── Recent reviews ─────────────────────────────────────────── */}
      <Card>
        <SectionHead
          icon={GitBranch}
          title="Recent reviews"
          action={
            <Link to="/reviews" className="text-xs font-semibold text-[#6d5dfb] hover:text-[#5b4de8] hover:underline">
              View all →
            </Link>
          }
        />
        <RecentReviews />
      </Card>

      {/* ── Danger zone ────────────────────────────────────────────── */}
      <div className="rounded-xl border border-red-200 bg-red-50/40 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-slate-800 mb-1">Danger zone</h3>
            <p className="text-sm text-slate-500 leading-relaxed">
              Permanently removes all review history, findings, and accept/dismiss feedback.
              Evaluation fixtures and source code are unaffected.
            </p>
          </div>
          <button
            onClick={() => setShowReset(true)}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-[13px] font-medium rounded-lg text-red-600 bg-white border border-slate-200 hover:bg-red-50 hover:text-red-700 hover:border-red-200 transition-all shadow-sm outline-none cursor-pointer"
          >
            <Trash2 size={14} aria-hidden />
            Reset review data
          </button>
        </div>
      </div>

      {/* Reset modal */}
      <ResetConfirmationModal
        open={showReset}
        onCancel={() => setShowReset(false)}
        onConfirm={() => resetMutation.mutate()}
        isLoading={resetMutation.isPending}
      />
    </div>
  );
}
