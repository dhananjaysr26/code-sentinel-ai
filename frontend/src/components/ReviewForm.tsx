import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import type { CreateReviewRequest, Review } from "../types";
import { reviewsApi } from "../api/client";

interface Props {
  onReviewComplete: (review: Review) => void;
}

export function ReviewForm({ onReviewComplete }: Props) {
  const [repoPath, setRepoPath] = useState("");
  const [baseRef, setBaseRef] = useState("HEAD~1");
  const [targetRef, setTargetRef] = useState("HEAD");
  const [llmProvider, setLlmProvider] = useState<"openai" | "bedrock">("bedrock");

  const mutation = useMutation({
    mutationFn: (req: CreateReviewRequest) => reviewsApi.createReview(req),
    onSuccess: (review) => {
      onReviewComplete(review);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoPath.trim()) return;
    mutation.mutate({
      repo_path: repoPath.trim(),
      base_ref: baseRef.trim() || "HEAD~1",
      target_ref: targetRef.trim() || "HEAD",
      llm_provider: llmProvider,
    });
  };

  return (
    <form className="review-form" onSubmit={handleSubmit}>
      <h2>Start Code Review</h2>

      <div className="form-group">
        <label htmlFor="repo-path">Repository Path</label>
        <input
          id="repo-path"
          type="text"
          value={repoPath}
          onChange={(e) => setRepoPath(e.target.value)}
          placeholder="/absolute/path/to/your/repo"
          required
          disabled={mutation.isPending}
        />
        <small>Absolute path to a local git repository</small>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label htmlFor="base-ref">Base Ref</label>
          <input
            id="base-ref"
            type="text"
            value={baseRef}
            onChange={(e) => setBaseRef(e.target.value)}
            placeholder="HEAD~1"
            disabled={mutation.isPending}
          />
        </div>
        <div className="form-group">
          <label htmlFor="target-ref">Target Ref</label>
          <input
            id="target-ref"
            type="text"
            value={targetRef}
            onChange={(e) => setTargetRef(e.target.value)}
            placeholder="HEAD"
            disabled={mutation.isPending}
          />
        </div>
      </div>


      <div className="form-group">
        <label htmlFor="llm-provider">AI Model Provider</label>
        <select
          id="llm-provider"
          value={llmProvider}
          onChange={(e) => setLlmProvider(e.target.value as "openai" | "bedrock")}
          disabled={mutation.isPending}
          className="form-select"
          style={{ width: "100%", padding: "0.5rem 0.75rem", borderRadius: "6px", border: "1px solid #d1d5db", background: "white" }}
        >
          <option value="openai">OpenAI (GPT-4o)</option>
          <option value="bedrock">AWS Bedrock (Claude 3.5 Sonnet)</option>
        </select>
      </div>

      <button
        type="submit"
        className="btn btn-primary"
        disabled={mutation.isPending || !repoPath.trim()}
      >
        {mutation.isPending ? "Running review…" : "Run Review"}
      </button>

      {mutation.isPending && (
        <p className="status-text">
          Analyzing diff and running AI review (this may take 30–60 seconds)…
        </p>
      )}

      {mutation.isError && (
        <div className="error-box">
          <strong>Review failed:</strong>{" "}
          {mutation.error instanceof Error
            ? mutation.error.message
            : "Unknown error"}
        </div>
      )}
    </form>
  );
}
