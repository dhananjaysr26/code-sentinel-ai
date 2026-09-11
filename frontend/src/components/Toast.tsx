import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export type ToastType = "success" | "error" | "info";

export interface ToastMessage {
  id: string;
  type: ToastType;
  message: string;
}

// Global toast state — simple pub/sub
type Listener = (toasts: ToastMessage[]) => void;
let _toasts: ToastMessage[] = [];
let _listeners: Listener[] = [];

function notify() {
  _listeners.forEach((fn) => fn([..._toasts]));
}

export function toast(type: ToastType, message: string) {
  const id = Math.random().toString(36).slice(2);
  _toasts = [..._toasts, { id, type, message }];
  notify();
  setTimeout(() => {
    _toasts = _toasts.filter((t) => t.id !== id);
    notify();
  }, 3500);
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    _listeners.push(setToasts);
    return () => {
      _listeners = _listeners.filter((fn) => fn !== setToasts);
    };
  }, []);

  const dismiss = (id: string) => {
    _toasts = _toasts.filter((t) => t.id !== id);
    notify();
  };

  return (
    <div
      className="fixed bottom-6 right-6 z-[999] flex flex-col gap-2 pointer-events-none"
      aria-live="polite"
      aria-label="Notifications"
    >
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: 12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.96 }}
            transition={{ duration: 0.2 }}
            className="pointer-events-auto flex items-center gap-3 bg-white border border-slate-200 shadow-lg rounded-xl px-4 py-3 min-w-[280px] max-w-sm"
          >
            {t.type === "success" && (
              <CheckCircle2 size={16} className="text-emerald-500 flex-shrink-0" />
            )}
            {t.type === "error" && (
              <XCircle size={16} className="text-red-500 flex-shrink-0" />
            )}
            <span className="text-sm text-slate-700 flex-1">{t.message}</span>
            <button
              onClick={() => dismiss(t.id)}
              className="text-slate-400 hover:text-slate-600 transition-colors"
              aria-label="Dismiss notification"
            >
              <X size={14} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
