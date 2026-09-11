import { useNavigate } from "react-router-dom";
import { ReviewForm } from "../../components/ReviewForm";
import type { Review } from "../../types";

export function ReviewPage() {
  const navigate = useNavigate();

  const handleReviewComplete = (completedReview: Review) => {
    navigate(`/review/${completedReview.id}`);
  };

  return (
    <div className="flex-1 flex flex-col justify-center items-center w-full max-w-2xl mx-auto pb-16">
      <div className="w-full">
        {/* ── Page header ───────────────────────────────────────────── */}
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
            New code review
          </h1>
          <p className="text-[15px] text-slate-500 mt-2">
            Point CodeSentinel AI at a local git repository to begin analysis.
          </p>
        </div>

        {/* ── Form card ───────────────────────────────────────────────── */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-200/30 p-8 md:p-10 w-full">
          <ReviewForm onReviewComplete={handleReviewComplete} />
        </div>
      </div>
    </div>
  );
}
