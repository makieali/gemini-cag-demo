"""Thin factory for the Gemini SDK client.

Isolated here so the rest of the package -- and the tests -- can depend on a
single seam that is trivial to construct or mock.
"""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def get_client(api_key: str):
    """Return a cached ``google.genai.Client`` for the given API key.

    Imported lazily so the package can be imported (and unit-tested) without the
    SDK installed or an API key present.
    """
    from google import genai

    return genai.Client(api_key=api_key)
