import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ReviewFinding, FeedbackAction } from "../types";
import { reviewsApi } from "../api/client";
import { SeverityBadge } from "./SeverityBadge";

interface Props {
  reviewId: string;
  finding: ReviewFinding;
}

// Category badge colours
const categoryStyles: Record<string, { bg: string; color: string; label: string }> = {
  security: { bg: "#7f1d1d", color: "#fca5a5", label: "🔒 Security" },
  correctness: { bg: "#1e3a5f", color: "#93c5fd", label: "🐛 Correctness" },
};

// Subcategory human-readable labels
const subcategoryLabels: Record<string, string> = {
  sql_injection: "SQL Injection",
  command_injection: "Command Injection",
  secret_exposure: "Secret Exposure",
  authorization: "Missing Authorization",
  input_validation: "Unsafe Input",
  null_dereference: "Null Dereference",
  off_by_one: "Off-by-One",
  logic_error: "Logic Error",
  resource_leak: "Resource Leak",
  missing_key_check: "Missing Key Check",
};

export function FindingCard({ reviewId, finding }: Props) {
  const queryClient = useQueryClient();
  const [localFeedback, setLocalFeedback] = useState<FeedbackAction>(
    finding.feedback
  );

  const feedbackMutation = useMutation({
    mutationFn: (action: "accept" | "dismiss") =>
      reviewsApi.submitFeedback(reviewId, finding.id, { action }),
    onSuccess: (updated) => {
      setLocalFeedback(updated.feedback);
      queryClient.invalidateQueries({ queryKey: ["review", reviewId] });
    },
  });

  const handleFeedback = (action: "accept" | "dismiss") => {
    if (feedbackMutation.isPending) return;
    feedbackMutation.mutate(action);
  };

  const feedbackLabel =
    localFeedback === "accept"
      ? "✓ Accepted"
      : localFeedback === "dismiss"
      ? "✗ Dismissed"
      : null;

  const catStyle = categoryStyles[finding.category] ?? categoryStyles["correctness"];
  const subcategoryLabel = finding.subcategory
    ? subcategoryLabels[finding.subcategory] ?? finding.subcategory
    : null;

  return (
    <div className={`finding-card finding-card--${finding.severity.toLowerCase()}`}>
      <div className="finding-card__header">
        <SeverityBadge severity={finding.severity} />

        {/* Category badge */}
        <span
          style={{
            background: catStyle.bg,
            color: catStyle.color,
            borderRadius: "4px",
            padding: "2px 8px",
            fontSize: "0.75rem",
            fontWeight: 600,
            marginLeft: "8px",
          }}
        >
          {catStyle.label}
        </span>

        {/* Subcategory badge */}
        {subcategoryLabel && (
          <span
            style={{
              background: "#27272a",
              color: "#a1a1aa",
              borderRadius: "4px",
              padding: "2px 8px",
              fontSize: "0.72rem",
              marginLeft: "6px",
            }}
          >
            {subcategoryLabel}
          </span>
        )}

        <span className="finding-card__confidence">
          Confidence: {(finding.confidence * 100).toFixed(0)}%
        </span>
      </div>

      <h3 className="finding-card__title">{finding.title}</h3>

      <div className="finding-card__location">
        <code>
          {finding.file}
          {finding.line !== null ? `:${finding.line}` : ""}
        </code>
        {finding.reviewer && (
          <span style={{ marginLeft: "10px", color: "#6b7280", fontSize: "0.8rem" }}>
            Reviewer: {finding.reviewer}
          </span>
        )}
      </div>

      <p className="finding-card__explanation">{finding.explanation}</p>

      {finding.evidence && (
        <pre className="finding-card__evidence">
          <code>{finding.evidence}</code>
        </pre>
      )}

      {finding.suggested_fix && (
        <div className="finding-card__fix">
          <strong>Suggested fix:</strong>
          <p>{finding.suggested_fix}</p>
        </div>
      )}

      <div className="finding-card__actions">
        {feedbackLabel ? (
          <span className="finding-card__feedback-label">{feedbackLabel}</span>
        ) : (
          <>
            <button
              className="btn btn-accept"
              onClick={() => handleFeedback("accept")}
              disabled={feedbackMutation.isPending}
            >
              Accept
            </button>
            <button
              className="btn btn-dismiss"
              onClick={() => handleFeedback("dismiss")}
              disabled={feedbackMutation.isPending}
            >
              Dismiss
            </button>
          </>
        )}
        {feedbackMutation.isError && (
          <span className="error-text">
            Failed to save feedback
          </span>
        )}
      </div>
    </div>
  );
}
