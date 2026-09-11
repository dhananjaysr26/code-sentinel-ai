/**
 * API client for CodeSentinel AI backend.
 *
 * All API calls go through this module.
 * The Vite dev server proxies /api to http://localhost:8000.
 */
import type {
  CreateReviewRequest,
  FeedbackRequest,
  Review,
  ReviewFinding,
  OverviewStats,
} from "../types";

const BASE_URL = "http://localhost:8000/api";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    let message = `API error ${res.status}`;
    try {
      const parsed = JSON.parse(body);
      message = parsed?.errors
        ? Object.values(parsed.errors).flat().join(", ")
        : parsed?.error ?? message;
    } catch {
      message = body || message;
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export const reviewsApi = {
  /**
   * POST /api/reviews/ — Trigger a new code review.
   * Note: This is a long-running operation (may take 30–120s).
   */
  createReview: async (request: CreateReviewRequest): Promise<Review> => {
    const res = await fetch(`${BASE_URL}/reviews/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    return handleResponse<Review>(res);
  },

  /**
   * GET /api/reviews/{id}/ — Retrieve a review with findings.
   */
  getReview: async (id: string): Promise<Review> => {
    const res = await fetch(`${BASE_URL}/reviews/${id}/`);
    return handleResponse<Review>(res);
  },

  /**
   * GET /api/reviews/list/ — List all reviews (most recent first).
   */
  listReviews: async (): Promise<Review[]> => {
    const res = await fetch(`${BASE_URL}/reviews/list/`);
    return handleResponse<Review[]>(res);
  },

  /**
   * POST /api/reviews/{id}/findings/{fid}/feedback/ — Record accept/dismiss.
   */
  submitFeedback: async (
    reviewId: string,
    findingId: string,
    request: FeedbackRequest
  ): Promise<ReviewFinding> => {
    const res = await fetch(
      `${BASE_URL}/reviews/${reviewId}/findings/${findingId}/feedback/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      }
    );
    return handleResponse<ReviewFinding>(res);
  },
};

export const overviewApi = {
  /**
   * GET /api/overview/ — Aggregate statistics.
   */
  getOverview: async (): Promise<OverviewStats> => {
    const res = await fetch(`${BASE_URL}/overview/`);
    return handleResponse<OverviewStats>(res);
  },

  /**
   * POST /api/overview/reset/ — Delete all reviews and findings.
   */
  reset: async (): Promise<{ deleted_reviews: number; deleted_findings: number }> => {
    const res = await fetch(`${BASE_URL}/overview/reset/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    return handleResponse(res);
  },
};
