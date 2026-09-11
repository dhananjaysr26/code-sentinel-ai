import { useState } from "react";
import { ReviewForm } from "../../components/ReviewForm";
import { ReviewResults } from "./ReviewResults";
import type { Review } from "../../types";

export function ReviewPage() {
  const [review, setReview] = useState<Review | null>(null);

  const handleReviewComplete = (completedReview: Review) => {
    setReview(completedReview);
  };

  const handleNewReview = () => {
    setReview(null);
  };

  return (
    <div className="review-page">
      <header className="app-header">
        <h1>CodeSentinel AI</h1>
        <p>AI-powered correctness review for your code changes</p>
      </header>

      <main className="app-main">
        {review === null ? (
          <ReviewForm onReviewComplete={handleReviewComplete} />
        ) : (
          <ReviewResults review={review} onNewReview={handleNewReview} />
        )}
      </main>
    </div>
  );
}
