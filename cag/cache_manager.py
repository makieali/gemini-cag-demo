"""Create and manage Gemini explicit context caches -- the heart of CAG.

A context cache loads the knowledge base (the uploaded documents + a system
instruction) into the model once. Every later query references the cache by
name via ``cached_content`` and is billed for the cached tokens at a deep
discount, instead of re-uploading and re-encoding the documents each time.
"""
from __future__ import annotations

from typing import Optional

from .models import KnowledgeBase, UploadedFile

# Minimum prompt tokens required before a cache can be created (Gemini 2.5).
MIN_CACHE_TOKENS = 2048

DEFAULT_SYSTEM_INSTRUCTION = (
    "You are a precise assistant answering questions strictly from the provided "
    "documents. Cite the relevant document when possible. If the answer is not "
    "in the documents, say so plainly instead of guessing."
)


class CacheTooSmallError(ValueError):
    """Raised when the documents are below the minimum token count for caching."""


def _file_parts(client, files: tuple[UploadedFile, ...]) -> list:
    """Build SDK content parts referencing already-uploaded Gemini files."""
    from google.genai import types

    parts = []
    for f in files:
        parts.append(types.Part.from_uri(file_uri=f.uri, mime_type=f.mime_type))
    return parts


def create_cache(
    client,
    model: str,
    files: tuple[UploadedFile, ...],
    ttl_seconds: int,
    display_name: str,
    system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION,
) -> KnowledgeBase:
    """Create a context cache from uploaded files and return a KnowledgeBase."""
    from google.genai import types

    config = types.CreateCachedContentConfig(
        display_name=display_name,
        system_instruction=system_instruction,
        contents=[types.Content(role="user", parts=_file_parts(client, files))],
        ttl=f"{ttl_seconds}s",
    )

    try:
        cache = client.caches.create(model=model, config=config)
    except Exception as exc:  # noqa: BLE001 - surface a friendly hint
        msg = str(exc)
        if "minimum" in msg.lower() or "token" in msg.lower():
            raise CacheTooSmallError(
                "Documents are too small to cache. Context caching needs at "
                f"least {MIN_CACHE_TOKENS} tokens of content."
            ) from exc
        raise

    usage = getattr(cache, "usage_metadata", None)
    cached_tokens = getattr(usage, "total_token_count", 0) if usage else 0

    return KnowledgeBase(
        cache_name=cache.name,
        model=model,
        display_name=display_name,
        files=files,
        cached_token_count=cached_tokens,
        created_at=_epoch(getattr(cache, "create_time", None)),
        expires_at=_epoch(getattr(cache, "expire_time", None)),
    )


def get_cache(client, cache_name: str):
    """Fetch cache metadata (raises if it has expired or was deleted)."""
    return client.caches.get(name=cache_name)


def extend_ttl(client, cache_name: str, ttl_seconds: int):
    """Push the expiry of an existing cache further into the future."""
    from google.genai import types

    return client.caches.update(
        name=cache_name,
        config=types.UpdateCachedContentConfig(ttl=f"{ttl_seconds}s"),
    )


def delete_cache(client, cache_name: str) -> None:
    """Delete a context cache so it stops incurring storage cost."""
    client.caches.delete(name=cache_name)


def _epoch(value) -> float:
    """Convert an SDK datetime (or None) to a unix timestamp."""
    if value is None:
        return 0.0
    try:
        return value.timestamp()
    except AttributeError:
        return 0.0
