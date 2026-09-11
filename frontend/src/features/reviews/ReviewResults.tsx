import type { Review } from "../../types";
import { FindingCard } from "../../components/FindingCard";

interface Props {
  review: Review;
  onNewReview: () => void;
}

export function ReviewResults({ review, onNewReview }: Props) {
  const { findings, status, repo_path, base_ref, target_ref, errors } = review;

  const hasFailed = status === "failed";
  const findingCount = findings.length;

  return (
    <div className="review-results">
      <div className="review-results__header">
        <div className="review-results__meta">
          <h2>Review Results</h2>
          <div className="review-meta-grid">
            <span className="meta-label">Repository:</span>
            <code className="meta-value">{repo_path}</code>
            <span className="meta-label">Diff:</span>
            <code className="meta-value">{base_ref}..{target_ref}</code>
            <span className="meta-label">Status:</span>
            <span className={`status-pill status-pill--${status}`}>{status}</span>
            <span className="meta-label">Findings:</span>
            <span className="meta-value">{findingCount}</span>
          </div>
        </div>
        <button className="btn btn-secondary" onClick={onNewReview}>
          New Review
        </button>
      </div>

      {hasFailed && errors.length > 0 && (
        <div className="error-box">
          <strong>Errors:</strong>
          <ul>
            {errors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {!hasFailed && findingCount === 0 && (
        <div className="no-findings">
          <p>✓ No correctness issues found in this diff.</p>
        </div>
      )}

      {findingCount > 0 && (
        <div className="findings-list">
          <h3>
            {findingCount} Finding{findingCount !== 1 ? "s" : ""}
          </h3>
          {findings.map((finding) => (
            <FindingCard
              key={finding.id}
              reviewId={review.id}
              finding={finding}
            />
          ))}
        </div>
      )}
    </div>
  );
}
