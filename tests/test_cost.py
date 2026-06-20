"""Tests for the pricing / savings logic -- the analytics centerpiece."""
from cag.cost import compute_cost, pricing_for, ModelPricing
from cag.models import TokenUsage


def test_pricing_lookup_tolerates_version_suffix():
    assert pricing_for("gemini-2.5-flash-001") is pricing_for("gemini-2.5-flash")


def test_pricing_unknown_model_falls_back():
    p = pricing_for("some-future-model")
    assert isinstance(p, ModelPricing)
    assert p.input_per_1m > 0


def test_cached_input_is_discounted():
    p = pricing_for("gemini-2.5-flash")
    assert p.cached_input_per_1m < p.input_per_1m
    # 90% discount -> cached costs 10% of full input rate
    assert round(p.cached_input_per_1m, 6) == round(p.input_per_1m * 0.10, 6)


def test_cost_with_cache_is_cheaper_than_without():
    usage = TokenUsage(
        prompt_tokens=100_000,   # mostly the cached documents
        cached_tokens=99_000,
        output_tokens=500,
        total_tokens=100_500,
    )
    cost = compute_cost(usage, "gemini-2.5-flash")
    assert cost.total_cost < cost.cost_without_cache
    assert cost.savings > 0
    assert 0 < cost.savings_pct < 100


def test_no_cache_means_no_savings():
    usage = TokenUsage(prompt_tokens=5000, cached_tokens=0, output_tokens=200, total_tokens=5200)
    cost = compute_cost(usage, "gemini-2.5-flash")
    assert cost.savings == 0
    assert cost.savings_pct == 0
    assert round(cost.total_cost, 8) == round(cost.cost_without_cache, 8)


def test_fresh_prompt_tokens_never_negative():
    usage = TokenUsage(prompt_tokens=10, cached_tokens=50)
    assert usage.fresh_prompt_tokens == 0
