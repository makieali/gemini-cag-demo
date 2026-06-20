"""Run queries against a knowledge base -- with a cache (CAG) or without it.

The ``answer_with_cache`` path is real Cache-Augmented Generation: it references
an existing context cache and only sends the user's question as fresh tokens.
``answer_full_context`` re-sends every document on each call and exists purely
so the UI can show the cost/latency difference side by side.
"""
from __future__ import annotations

import time
from typing import Iterator

from .cost import compute_cost
from .models import KnowledgeBase, QueryResult, TokenUsage


def _parse_usage(usage_metadata) -> TokenUsage:
    """Normalise the SDK's usage_metadata into our TokenUsage model."""
    if usage_metadata is None:
        return TokenUsage()
    prompt = getattr(usage_metadata, "prompt_token_count", 0) or 0
    cached = getattr(usage_metadata, "cached_content_token_count", 0) or 0
    output = getattr(usage_metadata, "candidates_token_count", 0) or 0
    total = getattr(usage_metadata, "total_token_count", 0) or (prompt + output)
    return TokenUsage(
        prompt_tokens=prompt,
        cached_tokens=cached,
        output_tokens=output,
        total_tokens=total,
    )


def answer_with_cache(
    client, knowledge_base: KnowledgeBase, question: str
) -> QueryResult:
    """Answer a question by reusing the knowledge base's context cache (CAG)."""
    from google.genai import types

    started = time.perf_counter()
    response = client.models.generate_content(
        model=knowledge_base.model,
        contents=question,
        config=types.GenerateContentConfig(cached_content=knowledge_base.cache_name),
    )
    latency_ms = (time.perf_counter() - started) * 1000

    usage = _parse_usage(getattr(response, "usage_metadata", None))
    return QueryResult(
        answer=response.text or "",
        usage=usage,
        cost=compute_cost(usage, knowledge_base.model),
        latency_ms=latency_ms,
        used_cache=True,
        model=knowledge_base.model,
    )


def answer_full_context(
    client, knowledge_base: KnowledgeBase, question: str
) -> QueryResult:
    """Answer the same question without a cache, re-sending all documents."""
    from google.genai import types

    parts = [types.Part.from_text(text=question)]
    for f in knowledge_base.files:
        parts.append(types.Part.from_uri(file_uri=f.uri, mime_type=f.mime_type))

    started = time.perf_counter()
    response = client.models.generate_content(
        model=knowledge_base.model,
        contents=[types.Content(role="user", parts=parts)],
    )
    latency_ms = (time.perf_counter() - started) * 1000

    usage = _parse_usage(getattr(response, "usage_metadata", None))
    return QueryResult(
        answer=response.text or "",
        usage=usage,
        cost=compute_cost(usage, knowledge_base.model),
        latency_ms=latency_ms,
        used_cache=False,
        model=knowledge_base.model,
    )


def stream_with_cache(
    client, knowledge_base: KnowledgeBase, question: str
) -> Iterator[str]:
    """Yield answer text chunks as they arrive, using the context cache."""
    from google.genai import types

    stream = client.models.generate_content_stream(
        model=knowledge_base.model,
        contents=question,
        config=types.GenerateContentConfig(cached_content=knowledge_base.cache_name),
    )
    for chunk in stream:
        if getattr(chunk, "text", None):
            yield chunk.text
