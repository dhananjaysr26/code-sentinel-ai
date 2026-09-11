"""Centralized pricing configuration for token usage."""

# Prices are per 1,000,000 tokens
MODEL_PRICING = {
    # Bedrock
    "us.meta.llama3-2-90b-instruct-v1:0": {"input": 0.72, "output": 0.72},
    "amazon.nova-pro-v1:0": {"input": 0.80, "output": 3.20},
    "amazon.nova-lite-v1:0": {"input": 0.06, "output": 0.24},
    "amazon.nova-micro-v1:0": {"input": 0.035, "output": 0.14},
    # DeepSeek example if supported on Bedrock
    "deepseek.v3-v1:0": {"input": 0.14, "output": 0.28},
    
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Calculate the estimated cost for a given model and token usage."""
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return None
    
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost

