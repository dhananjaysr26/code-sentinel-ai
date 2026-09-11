import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ReviewFinding, FeedbackAction } from "../types";
import { reviewsApi } from "../api/client";
import { SeverityBadge } from "./SeverityBadge";

interface Props {
  reviewId: string;
  finding: ReviewFinding;
}

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
      // Invalidate the review query so the parent re-fetches
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

  return (
    <div className={`finding-card finding-card--${finding.severity.toLowerCase()}`}>
      <div className="finding-card__header">
        <SeverityBadge severity={finding.severity} />
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
