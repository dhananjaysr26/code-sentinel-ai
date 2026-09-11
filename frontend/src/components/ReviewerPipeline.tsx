import { CheckCircle2, Loader2, XCircle, Circle } from "lucide-react";

interface Step {
  label: string;
  status: "completed" | "running" | "failed" | "pending";
}

interface ReviewerPipelineProps {
  isRunning?: boolean;
}

const DONE_STEPS: Step[] = [
  { label: "Diff extraction",   status: "completed" },
  { label: "Context assembly",  status: "completed" },
  { label: "Correctness review",status: "completed" },
  { label: "Security review",   status: "completed" },
  { label: "Merge & rank",      status: "completed" },
];

const RUNNING_STEPS: Step[] = [
  { label: "Diff extraction",   status: "completed" },
  { label: "Context assembly",  status: "running"   },
  { label: "Correctness review",status: "pending"   },
  { label: "Security review",   status: "pending"   },
  { label: "Merge & rank",      status: "pending"   },
];

const ICON: Record<Step["status"], React.ReactNode> = {
  completed: <CheckCircle2 size={14} className="text-emerald-500 flex-shrink-0" aria-hidden />,
  running:   <Loader2      size={14} className="text-[#6d5dfb] animate-spin flex-shrink-0" aria-hidden />,
  failed:    <XCircle      size={14} className="text-red-500 flex-shrink-0" aria-hidden />,
  pending:   <Circle       size={14} className="text-slate-300 flex-shrink-0" aria-hidden />,
};

export function ReviewerPipeline({ isRunning = false }: ReviewerPipelineProps) {
  const steps = isRunning ? RUNNING_STEPS : DONE_STEPS;

  return (
    <div>
      <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-4">
        Agent pipeline
      </p>
      <ul className="space-y-3" aria-label="Agent pipeline status">
        {steps.map((step) => (
          <li key={step.label} className="flex items-center gap-3">
            {ICON[step.status]}
            <span className={[
              "text-sm leading-none",
              step.status === "completed" ? "text-slate-600"                  : "",
              step.status === "running"   ? "text-slate-900 font-semibold"    : "",
              step.status === "failed"    ? "text-red-600"                    : "",
              step.status === "pending"   ? "text-slate-400"                  : "",
            ].filter(Boolean).join(" ")}>
              {step.label}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
