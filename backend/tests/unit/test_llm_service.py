import pytest
from sentinel.services.llm_service import _normalize_usage, LLMUsage
from sentinel.services.pricing import calculate_cost, MODEL_PRICING

class MockRawMessageOpenAI:
    def __init__(self, in_t, out_t):
        self.usage_metadata = {
            "input_tokens": in_t,
            "output_tokens": out_t,
            "total_tokens": in_t + out_t
        }

class MockRawMessageBedrock:
    def __init__(self, in_t, out_t):
        self.response_metadata = {
            "amazon-bedrock-invocationMetrics": {
                "inputTokenCount": in_t,
                "outputTokenCount": out_t
            }
        }
        self.usage_metadata = None

def test_cost_calculation():
    # Bedrock example
    cost = calculate_cost("amazon.nova-pro-v1:0", 1000000, 1000000)
    assert cost == 4.00 # 0.80 + 3.20
    
    # OpenAI example
    cost = calculate_cost("gpt-4o", 1_000_000, 1_000_000)
    assert cost == 12.50 # 2.50 + 10.00
    
    # Missing pricing
    assert calculate_cost("nonexistent.model", 100, 100) is None

def test_openai_usage_normalization():
    msg = MockRawMessageOpenAI(100, 20)
    usage = _normalize_usage("openai", "gpt-4o", msg, 500)
    
    assert usage.input_tokens == 100
    assert usage.output_tokens == 20
    assert usage.total_tokens == 120
    assert usage.latency_ms == 500
    assert usage.provider == "openai"
    assert usage.estimated_cost == (100 / 1_000_000 * 2.50) + (20 / 1_000_000 * 10.0)

def test_bedrock_usage_normalization():
    msg = MockRawMessageBedrock(200, 50)
    usage = _normalize_usage("bedrock", "amazon.nova-lite-v1:0", msg, 1200)
    
    assert usage.input_tokens == 200
    assert usage.output_tokens == 50
    assert usage.total_tokens == 250
    assert usage.latency_ms == 1200
    assert usage.provider == "bedrock"
    assert usage.estimated_cost == (200 / 1_000_000 * 0.06) + (50 / 1_000_000 * 0.24)

def test_missing_usage_metadata():
    usage = _normalize_usage("openai", "gpt-4o", object(), 300)
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0
    assert usage.total_tokens == 0
    assert usage.estimated_cost == 0.0

def test_missing_pricing_graceful_handling():
    msg = MockRawMessageOpenAI(100, 100)
    usage = _normalize_usage("openai", "unknown-model", msg, 200)
    assert usage.estimated_cost is None
    assert usage.input_tokens == 100
