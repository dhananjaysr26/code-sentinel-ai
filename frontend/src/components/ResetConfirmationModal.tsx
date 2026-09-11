import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";

interface ResetConfirmationModalProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  isLoading?: boolean;
}

export function ResetConfirmationModal({
  open,
  onCancel,
  onConfirm,
  isLoading = false,
}: ResetConfirmationModalProps) {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const confirmed = input === "RESET";

  // Reset input and focus when modal opens
  useEffect(() => {
    if (open) {
      setInput("");
      setTimeout(() => inputRef.current?.focus(), 80);
    }
  }, [open]);

  // Trap Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open && !isLoading) onCancel();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, isLoading, onCancel]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-[2px]"
            aria-hidden
            onClick={!isLoading ? onCancel : undefined}
          />

          {/* Dialog */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="reset-modal-title"
              className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-start justify-between px-6 pt-6 pb-4">
                <div className="flex items-start gap-4">
                  <div className="w-11 h-11 rounded-xl bg-red-50 border border-red-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <AlertTriangle size={20} className="text-red-500" />
                  </div>
                  <div>
                    <h2 id="reset-modal-title" className="text-lg font-semibold text-slate-900 tracking-tight">
                      Reset review data?
                    </h2>
                    <p className="text-sm text-slate-500 mt-1 leading-relaxed">
                      This action cannot be undone.
                    </p>
                  </div>
                </div>
                {!isLoading && (
                  <button
                    onClick={onCancel}
                    aria-label="Close dialog"
                    className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors -mt-1 -mr-2 p-1.5 rounded-lg"
                  >
                    <X size={18} />
                  </button>
                )}
              </div>

              {/* Body */}
              <div className="px-6 pb-6 space-y-5">
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                  <p className="text-sm font-semibold text-slate-700 mb-2.5">This will permanently delete:</p>
                  <ul className="text-sm text-slate-600 space-y-2">
                    <li className="flex items-center gap-2.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-400 flex-shrink-0" />
                      All review history
                    </li>
                    <li className="flex items-center gap-2.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-400 flex-shrink-0" />
                      All findings
                    </li>
                    <li className="flex items-center gap-2.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-400 flex-shrink-0" />
                      All accept / dismiss feedback
                    </li>
                  </ul>
                  <div className="border-t border-slate-200 mt-3 pt-3">
                    <p className="text-xs text-slate-500 leading-relaxed">
                      Evaluation fixtures and application source code will <span className="font-semibold text-slate-600">not</span> be affected.
                    </p>
                  </div>
                </div>

                {/* Confirmation input */}
                <div>
                  <label
                    htmlFor="reset-confirm-input"
                    className="flex items-center gap-1.5 text-sm font-medium text-slate-700 mb-2"
                  >
                    Type <code className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 font-mono text-[11px] font-bold tracking-widest border border-slate-200">RESET</code> to confirm
                  </label>
                  <input
                    id="reset-confirm-input"
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    disabled={isLoading}
                    placeholder="RESET"
                    autoComplete="off"
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-red-400/30 focus:border-red-400 transition-all placeholder-slate-300 disabled:opacity-50 shadow-sm"
                  />
                </div>

                <div className="flex items-center justify-end gap-2.5 pt-3">
                  <button
                    onClick={onCancel}
                    disabled={isLoading}
                    className="inline-flex items-center justify-center gap-2 px-4 py-2.5 text-[13px] font-medium rounded-lg text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 hover:border-slate-300 transition-all shadow-sm outline-none cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={onConfirm}
                    disabled={!confirmed || isLoading}
                    className="inline-flex items-center justify-center gap-2 px-4 py-2.5 text-[13px] font-medium rounded-lg text-red-600 bg-white border border-slate-200 hover:bg-red-50 hover:text-red-700 hover:border-red-200 transition-all shadow-sm outline-none cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                    aria-disabled={!confirmed}
                  >
                    {isLoading ? "Resetting..." : "Reset data"}
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
