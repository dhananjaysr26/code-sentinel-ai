import type { Finding } from "../types";
import { BlockRenderer } from "./BlockRenderer";
import { Check, X, User, Code2 } from "lucide-react";
import { toast } from "./Toast";

interface FindingCardProps {
  finding: Finding;
  onStatusChange: (id: string, action: "accept" | "dismiss") => void;
  isSelected?: boolean;
  onClick?: () => void;
}

const SEVERITY_LEFT: Record<string, string> = {
  CRITICAL: "border-l-red-500",
  HIGH:     "border-l-orange-400",
  MEDIUM:   "border-l-amber-400",
  LOW:      "border-l-blue-400",
};

export function FindingCard({ finding, onStatusChange, isSelected, onClick }: FindingCardProps) {
  const blocks = [
    { type: "header",   title: finding.title,        severity: finding.severity, file: finding.file, line: finding.line },
    { type: "diff",     evidence: finding.evidence },
    { type: "rationale",explanation: finding.explanation, suggested_fix: finding.suggested_fix },
    { type: "metadata", confidence: finding.confidence, source: finding.source, category: finding.category },
  ];

  const isAccepted  = finding.feedback === "accept";
  const isDismissed = finding.feedback === "dismiss";

  const handleAccept = (e: React.MouseEvent) => {
    e.stopPropagation();
    onStatusChange(finding.id, "accept");
    toast("success", "Finding accepted");
  };

  const handleDismiss = (e: React.MouseEvent) => {
    e.stopPropagation();
    onStatusChange(finding.id, "dismiss");
    toast("info", "Finding dismissed");
  };

  return (
    <article
      onClick={onClick}
      className={[
        // base card
        "bg-white rounded-xl border border-l-4 border-slate-200",
        "shadow-[0_1px_3px_0_rgba(15,23,42,0.06),0_1px_2px_-1px_rgba(15,23,42,0.04)]",
        "overflow-hidden transition-all duration-200",
        // left border per severity
        SEVERITY_LEFT[finding.severity] ?? "border-l-slate-300",
        // selected ring
        isSelected ? "ring-2 ring-[#6d5dfb]/30" : "",
        // hover if clickable
        onClick ? "cursor-pointer hover:shadow-[0_4px_12px_0_rgba(15,23,42,0.10)] hover:border-slate-300" : "",
        // dimmed when dismissed
        isDismissed ? "opacity-55" : "",
      ].filter(Boolean).join(" ")}
      aria-label={`Finding: ${finding.title}`}
    >
      {/* Rendered content blocks */}
      {blocks.map((block, i) => (
        <BlockRenderer key={i} rawBlock={block} />
      ))}

      {/* ── Footer: reviewer tag + actions ─────────────────────────── */}
      <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/70 flex items-center justify-between gap-3">
        {/* Reviewer or Linter */}
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          {finding.source === "linter" ? (
            <>
              <Code2 size={11} aria-hidden />
              <span className="capitalize font-medium">Linter</span>
              {finding.subcategory && (
                <span className="ml-1 text-slate-500 font-mono px-1.5 py-0.5 bg-slate-100 rounded-sm">
                  {finding.subcategory}
                </span>
              )}
            </>
          ) : finding.reviewer ? (
            <>
              <User size={11} aria-hidden />
              <span className="capitalize font-medium">{finding.reviewer} Reviewer</span>
            </>
          ) : (
            <span>Unknown Reviewer</span>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleDismiss}
            disabled={isDismissed}
            aria-label={isDismissed ? "Finding dismissed" : "Dismiss finding"}
            aria-pressed={isDismissed}
            className={isDismissed ? "inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-[12px] font-semibold rounded-lg text-slate-400 bg-slate-50 border border-slate-200 cursor-default opacity-60" : "inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-[12px] font-semibold rounded-lg text-slate-700 bg-white border border-slate-200 hover:bg-red-50 hover:text-red-700 hover:border-red-200 transition-all shadow-sm outline-none"}
          >
            <X size={13} />
            {isDismissed ? "Dismissed" : "Dismiss"}
          </button>

          <button
            onClick={handleAccept}
            disabled={isAccepted}
            aria-label={isAccepted ? "Finding accepted" : "Accept finding"}
            aria-pressed={isAccepted}
            className={isAccepted ? "inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-[12px] font-semibold rounded-lg text-emerald-700 bg-emerald-50 border border-emerald-200 cursor-default opacity-70" : "inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-[12px] font-semibold rounded-lg text-white bg-gradient-to-b from-indigo-500 to-indigo-600 border border-indigo-700 shadow-sm hover:from-indigo-600 hover:to-indigo-700 active:from-indigo-700 active:to-indigo-700 transition-all outline-none"}
          >
            <Check size={13} />
            {isAccepted ? "Accepted ✓" : "Accept"}
          </button>
        </div>
      </div>
    </article>
  );
}
