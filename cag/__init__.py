"""Cache-Augmented Generation (CAG) toolkit for the Gemini API.

This package implements *true* CAG: documents are loaded once into a Gemini
explicit context cache (``client.caches.create``), and every subsequent query
reuses that cache via ``cached_content``. Cached input tokens are billed at a
deep discount, so repeated questions over the same knowledge base are far
cheaper and lower-latency than re-sending the documents each time.
"""

__all__ = [
    "models",
    "cost",
    "files",
    "client",
    "cache_manager",
    "generation",
]
