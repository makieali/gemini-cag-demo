"""Immutable data models shared across the CAG package.

Every model is a frozen dataclass: operations return new instances rather than
mutating existing ones, which keeps token/cost accounting free of hidden state.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional


@dataclass(frozen=True)
class UploadedFile:
    """A file that has been uploaded to the Gemini Files API."""

    name: str           # Gemini resource name, e.g. "files/abc123"
    uri: str            # Full URI used in generate_content / cache contents
    mime_type: str
    original_filename: str
    size_bytes: int


@dataclass(frozen=True)
class TokenUsage:
    """Token accounting for a single generation call."""

    prompt_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    @property
    def fresh_prompt_tokens(self) -> int:
        """Prompt tokens that were NOT served from cache (billed at full rate)."""
        return max(self.prompt_tokens - self.cached_tokens, 0)


@dataclass(frozen=True)
class CostBreakdown:
    """Cost of a single call, plus the counterfactual cost without caching."""

    cached_input_cost: float = 0.0
    fresh_input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    # What the same call would have cost with no cache (all prompt tokens fresh).
    cost_without_cache: float = 0.0

    @property
    def savings(self) -> float:
        return max(self.cost_without_cache - self.total_cost, 0.0)

    @property
    def savings_pct(self) -> float:
        if self.cost_without_cache <= 0:
            return 0.0
        return (self.savings / self.cost_without_cache) * 100.0


@dataclass(frozen=True)
class QueryResult:
    """The full result of one question against a knowledge base."""

    answer: str
    usage: TokenUsage
    cost: CostBreakdown
    latency_ms: float
    used_cache: bool
    model: str


@dataclass(frozen=True)
class KnowledgeBase:
    """A cached knowledge base: a Gemini context cache plus its source files."""

    cache_name: str                 # "cachedContents/..." resource name
    model: str
    display_name: str
    files: tuple[UploadedFile, ...] = ()
    cached_token_count: int = 0
    created_at: float = 0.0
    expires_at: float = 0.0

    def with_files(self, files: tuple[UploadedFile, ...]) -> "KnowledgeBase":
        return replace(self, files=files)
