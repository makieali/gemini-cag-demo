"""Aggregate per-query results into cumulative CAG savings statistics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import QueryResult


@dataclass(frozen=True)
class SessionStats:
    """Cumulative stats across all queries in a knowledge-base session."""

    query_count: int = 0
    total_cost: float = 0.0
    total_cost_without_cache: float = 0.0
    total_cached_tokens: int = 0
    total_output_tokens: int = 0

    @property
    def total_savings(self) -> float:
        return max(self.total_cost_without_cache - self.total_cost, 0.0)

    @property
    def savings_pct(self) -> float:
        if self.total_cost_without_cache <= 0:
            return 0.0
        return (self.total_savings / self.total_cost_without_cache) * 100.0

    def add(self, result: QueryResult) -> "SessionStats":
        """Return a new SessionStats including ``result`` (immutable update)."""
        return SessionStats(
            query_count=self.query_count + 1,
            total_cost=self.total_cost + result.cost.total_cost,
            total_cost_without_cache=(
                self.total_cost_without_cache + result.cost.cost_without_cache
            ),
            total_cached_tokens=self.total_cached_tokens + result.usage.cached_tokens,
            total_output_tokens=self.total_output_tokens + result.usage.output_tokens,
        )


def summarize(results: Iterable[QueryResult]) -> SessionStats:
    """Fold a sequence of query results into a single SessionStats."""
    stats = SessionStats()
    for result in results:
        stats = stats.add(result)
    return stats
