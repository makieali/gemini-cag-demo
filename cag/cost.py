"""Pricing and cost accounting for Gemini calls.

Prices are expressed in USD per 1,000,000 tokens and are intentionally kept in
one place so they are easy to audit and update. They are approximate and may
lag the official pricing page -- always verify current rates at
https://ai.google.dev/pricing before relying on these numbers.

The key CAG idea this module encodes: cached input tokens are billed at a deep
discount (90% off for Gemini 2.5+), so the cost of a query that reuses a cache
is much lower than the same query with the documents re-sent every time.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import CostBreakdown, TokenUsage


@dataclass(frozen=True)
class ModelPricing:
    """USD per 1M tokens for a given model."""

    input_per_1m: float
    output_per_1m: float
    # Discount applied to cached input tokens (0.90 == 90% cheaper).
    cache_discount: float = 0.90

    @property
    def cached_input_per_1m(self) -> float:
        return self.input_per_1m * (1.0 - self.cache_discount)


# Approximate public pricing (USD / 1M tokens). Update from ai.google.dev/pricing.
PRICING: dict[str, ModelPricing] = {
    "gemini-2.5-flash": ModelPricing(input_per_1m=0.30, output_per_1m=2.50, cache_discount=0.90),
    "gemini-2.5-pro": ModelPricing(input_per_1m=1.25, output_per_1m=10.00, cache_discount=0.90),
    "gemini-2.0-flash": ModelPricing(input_per_1m=0.10, output_per_1m=0.40, cache_discount=0.75),
}

_DEFAULT_PRICING = ModelPricing(input_per_1m=0.30, output_per_1m=2.50, cache_discount=0.90)


def pricing_for(model: str) -> ModelPricing:
    """Look up pricing for a model, tolerating version suffixes like '-001'."""
    if model in PRICING:
        return PRICING[model]
    for known, price in PRICING.items():
        if model.startswith(known):
            return price
    return _DEFAULT_PRICING


def _cost(tokens: int, per_1m: float) -> float:
    return (tokens / 1_000_000) * per_1m


def compute_cost(usage: TokenUsage, model: str) -> CostBreakdown:
    """Compute the actual cost of a call and its no-cache counterfactual."""
    price = pricing_for(model)

    cached_input_cost = _cost(usage.cached_tokens, price.cached_input_per_1m)
    fresh_input_cost = _cost(usage.fresh_prompt_tokens, price.input_per_1m)
    output_cost = _cost(usage.output_tokens, price.output_per_1m)
    total = cached_input_cost + fresh_input_cost + output_cost

    # Counterfactual: if nothing were cached, every prompt token costs full rate.
    cost_without_cache = (
        _cost(usage.prompt_tokens, price.input_per_1m) + output_cost
    )

    return CostBreakdown(
        cached_input_cost=cached_input_cost,
        fresh_input_cost=fresh_input_cost,
        output_cost=output_cost,
        total_cost=total,
        cost_without_cache=cost_without_cache,
    )
