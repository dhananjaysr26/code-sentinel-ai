/**
 * TypeScript types matching the backend API schema.
 * These types are the single source of truth for the frontend/backend contract.
 */

export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type Category = "correctness";
export type Source = "llm" | "linter" | "ast";
export type ReviewStatus = "pending" | "running" | "completed" | "failed";
export type FeedbackAction = "accept" | "dismiss" | "none";

export interface ReviewFinding {
  id: string;
  file: string;
  line: number | null;
  title: string;
  category: Category;
  severity: Severity;
  confidence: number;
  explanation: string;
  evidence: string;
  suggested_fix: string | null;
  source: Source;
  feedback: FeedbackAction;
  created_at: string;
}

export interface Review {
  id: string;
  repo_path: string;
  base_ref: string;
  target_ref: string;
  status: ReviewStatus;
  raw_diff: string;
  errors: string[];
  review_metadata: Record<string, unknown>;
  findings: ReviewFinding[];
  created_at: string;
  updated_at: string;
}

export interface CreateReviewRequest {
  repo_path: string;
  base_ref: string;
  target_ref: string;
  llm_provider: "openai" | "bedrock";
}

export interface FeedbackRequest {
  action: "accept" | "dismiss";
}
