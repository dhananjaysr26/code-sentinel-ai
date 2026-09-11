import { PackageOpen, FileSearch, MessageSquareDashed } from "lucide-react";

type EmptyType = "no-reviews" | "no-findings" | "no-feedback" | "generic";

interface EmptyStateProps {
  type?: EmptyType;
  title?: string;
  description?: string;
  action?: React.ReactNode;
}

const PRESETS: Record<
  EmptyType,
  { Icon: React.ElementType; title: string; description: string }
> = {
  "no-reviews": {
    Icon: PackageOpen,
    title: "No reviews yet",
    description: "Run your first review to populate CodeSentinel AI.",
  },
  "no-findings": {
    Icon: FileSearch,
    title: "No issues found",
    description: "The selected diff did not produce any findings.",
  },
  "no-feedback": {
    Icon: MessageSquareDashed,
    title: "No developer feedback yet",
    description: "Accept or dismiss findings to provide feedback.",
  },
  generic: {
    Icon: PackageOpen,
    title: "Nothing here",
    description: "No data available.",
  },
};

export function EmptyState({
  type = "generic",
  title,
  description,
  action,
}: EmptyStateProps) {
  const preset = PRESETS[type];
  const { Icon } = preset;
  const heading = title ?? preset.title;
  const body = description ?? preset.description;

  return (
    <div className="flex flex-col items-center justify-center py-16 px-8 text-center">
      <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
        <Icon size={22} className="text-slate-400" />
      </div>
      <h3 className="text-sm font-semibold text-slate-700 mb-1">{heading}</h3>
      <p className="text-sm text-slate-500 max-w-xs">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
