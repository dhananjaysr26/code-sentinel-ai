export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface CreateReviewRequest {
  repo_path: string;
  base_ref: string;
  target_ref: string;
  llm_provider: "openai" | "bedrock";
}

export interface FeedbackRequest {
  action: "accept" | "dismiss";
}

export interface ReviewFinding {
  id: string;
  file: string;
  line: number | null;
  title: string;
  category: string;
  subcategory?: string;
  reviewer?: string;
  severity: Severity;
  confidence: number;
  explanation: string;
  evidence: string;
  suggested_fix?: string;
  source: string;
  feedback?: "none" | "accept" | "dismiss";
  created_at?: string;
}

export interface Finding extends ReviewFinding {}

export interface Review {
  id: string;
  repo_path: string;
  base_ref: string;
  target_ref: string;
  status: "pending" | "running" | "completed" | "failed";
  findings: Finding[];
  raw_diff?: string;
  errors?: string[];
  review_metadata?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
}

export interface OverviewStats {
  total_reviews: number;
  total_findings: number;
  accepted: number;
  dismissed: number;
  unreviewed: number;
  acceptance_rate: number;
  severity_distribution: Record<string, number>;
  reviewer_distribution: Record<string, number>;
  evaluation: {
    precision: number;
    recall: number;
    f1: number;
    seeded_total: number;
    seeded_detected: number;
  };
}
