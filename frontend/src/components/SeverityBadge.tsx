import type { Severity } from "../types";

const SEVERITY_STYLES: Record<Severity, string> = {
  CRITICAL: "badge badge-critical",
  HIGH: "badge badge-high",
  MEDIUM: "badge badge-medium",
  LOW: "badge badge-low",
};

interface Props {
  severity: Severity;
}

export function SeverityBadge({ severity }: Props) {
  return (
    <span className={SEVERITY_STYLES[severity]}>
      {severity}
    </span>
  );
}
