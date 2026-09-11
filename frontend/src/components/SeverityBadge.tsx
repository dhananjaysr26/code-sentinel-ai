import type { Severity } from "../types";
import { ShieldAlert, AlertTriangle, AlertCircle, Info } from "lucide-react";

interface SeverityBadgeProps {
  severity: Severity;
  showIcon?: boolean;
  size?: "sm" | "md";
}

const CONFIG: Record<
  Severity,
  { label: string; classes: string; Icon: React.ElementType }
> = {
  CRITICAL: {
    label: "Critical",
    classes: "bg-red-50 text-red-700 border border-red-200",
    Icon: ShieldAlert,
  },
  HIGH: {
    label: "High",
    classes: "bg-orange-50 text-orange-700 border border-orange-200",
    Icon: AlertTriangle,
  },
  MEDIUM: {
    label: "Medium",
    classes: "bg-amber-50 text-amber-700 border border-amber-200",
    Icon: AlertCircle,
  },
  LOW: {
    label: "Low",
    classes: "bg-blue-50 text-blue-700 border border-blue-200",
    Icon: Info,
  },
};

export function SeverityBadge({
  severity,
  showIcon = true,
  size = "sm",
}: SeverityBadgeProps) {
  const { label, classes, Icon } = CONFIG[severity] ?? CONFIG.LOW;
  const textSize = size === "sm" ? "text-xs" : "text-sm";
  const iconSize = size === "sm" ? 11 : 13;
  const padding = size === "sm" ? "px-2 py-0.5" : "px-2.5 py-1";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md font-semibold ${textSize} ${padding} ${classes}`}
      aria-label={`Severity: ${label}`}
    >
      {showIcon && <Icon size={iconSize} />}
      {label}
    </span>
  );
}
