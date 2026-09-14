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

export interface LLMCallUsage {
  reviewer: string;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  estimated_cost: number | null;
  status: string;
}

export interface ReviewUsage {
  provider: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_latency_ms: number;
  total_estimated_cost?: number | null;
  llm_calls: number;
  tool_calls: number;
  iterations: number;
  models_used: string[];
}

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
  usage?: ReviewUsage;
  reviewer_usage?: LLMCallUsage[];
  created_at: string;
  updated_at?: string;
}

export interface OverviewStats {
  total_reviews: number;
  total_findings: number;
  linter_findings?: number;
  accepted: number;
  dismissed: number;
  unreviewed: number;
  acceptance_rate: number;
  severity_distribution: Record<string, number>;
  reviewer_distribution: Record<string, number>;
  usage_metrics?: {
    avg_tokens: number;
    avg_latency_s: number;
    avg_cost: number | null;
    total_calls: number;
    total_tool_calls: number;
  };
  evaluation: {
    precision: number;
    recall: number;
    f1: number;
    seeded_total: number;
    seeded_detected: number;
  };
}
