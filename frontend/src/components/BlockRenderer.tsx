import { useState } from "react";
import {
  BlockSchema,
  type HeaderBlock,
  type DiffBlock,
  type RationaleBlock,
  type MetadataBlock,
} from "../schema/blocks";
import { SeverityBadge } from "./SeverityBadge";
import { ConfidenceIndicator } from "./ConfidenceIndicator";
import {
  Code2, ChevronDown, Lightbulb, AlertTriangle, MapPin, Tag,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// ─────────────────────────────────────────────────────────────────────────────
// Header block — title, severity, file path
// ─────────────────────────────────────────────────────────────────────────────
function HeaderBlockComponent({ block }: { block: HeaderBlock }) {
  return (
    <div className="px-6 pt-6 pb-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0 space-y-2">
          <SeverityBadge severity={block.severity} size="sm" />
          <h3 className="text-[15px] font-semibold text-slate-900 leading-snug">
            {block.title}
          </h3>
          {block.file && (
            <div className="flex items-center gap-1.5 text-slate-400">
              <MapPin size={11} className="flex-shrink-0" aria-hidden />
              <span className="text-xs font-mono truncate">
                {block.file}
                {block.line != null ? <span className="text-slate-500">:{block.line}</span> : null}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Diff / evidence block
// ─────────────────────────────────────────────────────────────────────────────
function DiffBlockComponent({ block }: { block: DiffBlock }) {
  if (!block.evidence) return null;
  return (
    <div className="mx-6 mb-5 rounded-xl overflow-hidden border border-slate-200">
      {/* Header bar */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-50 border-b border-slate-200">
        <Code2 size={12} className="text-slate-400" aria-hidden />
        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
          Vulnerable code
        </span>
      </div>
      {/* Code */}
      <div className="overflow-x-auto">
        <pre className="px-5 py-4 text-xs font-mono text-red-700 bg-red-50 leading-6 whitespace-pre-wrap">
          {block.evidence}
        </pre>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Rationale — expandable
// ─────────────────────────────────────────────────────────────────────────────
function RationaleBlockComponent({ block }: { block: RationaleBlock }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mx-6 mb-5 rounded-xl border border-slate-200 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls="rationale-body"
        className="w-full flex items-center gap-2.5 px-4 py-3.5 text-left bg-white hover:bg-slate-50 transition-colors"
      >
        <Lightbulb size={13} className="text-amber-500 flex-shrink-0" aria-hidden />
        <span className="text-sm font-semibold text-slate-700 flex-1">
          Why this is a problem
        </span>
        <motion.div
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.18 }}
          className="flex-shrink-0"
        >
          <ChevronDown size={14} className="text-slate-400" aria-hidden />
        </motion.div>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id="rationale-body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeInOut" }}
            className="overflow-hidden border-t border-slate-200"
          >
            <div className="px-5 py-4 space-y-4 bg-white">
              <p className="text-sm text-slate-600 leading-relaxed">{block.explanation}</p>

              {block.suggested_fix && (
                <div className="rounded-xl overflow-hidden border border-emerald-200">
                  <div className="flex items-center gap-2 px-4 py-2.5 bg-emerald-50 border-b border-emerald-200">
                    <span className="text-[11px] font-bold text-emerald-700 uppercase tracking-wider">
                      Suggested fix
                    </span>
                  </div>
                  <pre className="px-5 py-4 text-xs font-mono text-emerald-800 bg-emerald-50/60 leading-6 whitespace-pre-wrap overflow-x-auto">
                    {block.suggested_fix}
                  </pre>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Metadata — confidence, category, source
// ─────────────────────────────────────────────────────────────────────────────
function MetadataBlockComponent({ block }: { block: MetadataBlock }) {
  return (
    <div className="px-6 pb-5 flex items-center flex-wrap gap-x-6 gap-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-500 font-medium">Confidence</span>
        <ConfidenceIndicator value={block.confidence} />
      </div>
      {block.category && (
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <Tag size={11} className="text-slate-400" aria-hidden />
          <span className="font-medium">{block.category}</span>
        </div>
      )}
      {block.source && (
        <span className="text-xs text-slate-400 ml-auto font-mono">
          via {block.source}
        </span>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Unknown block fallback
// ─────────────────────────────────────────────────────────────────────────────
function UnknownBlockComponent({ rawData }: { rawData: unknown }) {
  return (
    <div className="mx-6 my-4 p-4 rounded-xl bg-amber-50 border border-amber-200">
      <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-amber-700">
        <AlertTriangle size={12} aria-hidden />
        Unknown block type
      </div>
      <pre className="text-[11px] text-amber-800 overflow-x-auto font-mono">
        {JSON.stringify(rawData, null, 2)}
      </pre>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Dispatcher
// ─────────────────────────────────────────────────────────────────────────────
export function BlockRenderer({ rawBlock }: { rawBlock: unknown }) {
  const parsed = BlockSchema.safeParse(rawBlock);
  if (!parsed.success) return <UnknownBlockComponent rawData={rawBlock} />;

  const block = parsed.data;
  switch (block.type) {
    case "header":   return <HeaderBlockComponent   block={block} />;
    case "diff":     return <DiffBlockComponent     block={block} />;
    case "rationale":return <RationaleBlockComponent block={block} />;
    case "metadata": return <MetadataBlockComponent  block={block} />;
    default:         return <UnknownBlockComponent   rawData={block} />;
  }
}
