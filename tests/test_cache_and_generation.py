"""Tests for cache creation, generation paths, and analytics."""
from cag import cache_manager, generation
from cag.analytics import SessionStats, summarize
from cag.models import KnowledgeBase, UploadedFile


def _file():
    return UploadedFile(
        name="files/abc", uri="https://gen.example/files/abc",
        mime_type="application/pdf", original_filename="doc.pdf", size_bytes=1234,
    )


def _kb():
    return KnowledgeBase(
        cache_name="cachedContents/test123",
        model="gemini-2.5-flash",
        display_name="kb",
        files=(_file(),),
    )


def test_create_cache_returns_knowledge_base(client):
    kb = cache_manager.create_cache(
        client, "gemini-2.5-flash", (_file(),),
        ttl_seconds=3600, display_name="kb",
    )
    assert isinstance(kb, KnowledgeBase)
    assert kb.cache_name == "cachedContents/test123"
    assert kb.cached_token_count == 5000
    assert len(client.caches.created) == 1


def test_delete_cache_calls_sdk(client):
    cache_manager.delete_cache(client, "cachedContents/test123")
    assert "cachedContents/test123" in client.caches.deleted


def test_answer_with_cache_reports_cached_tokens(client):
    result = generation.answer_with_cache(client, _kb(), "What is this about?")
    assert result.used_cache is True
    assert result.usage.cached_tokens == 5000
    assert result.usage.fresh_prompt_tokens == 200  # 5200 prompt - 5000 cached
    assert result.cost.savings > 0
    assert result.latency_ms >= 0


def test_full_context_has_no_cached_tokens(client):
    result = generation.answer_full_context(client, _kb(), "What is this about?")
    assert result.used_cache is False
    assert result.usage.cached_tokens == 0
    assert result.cost.savings == 0


def test_cag_cheaper_than_full_context(client):
    kb = _kb()
    cag = generation.answer_with_cache(client, kb, "q")
    full = generation.answer_full_context(client, kb, "q")
    assert cag.cost.total_cost < full.cost.total_cost


def test_stream_with_cache_yields_chunks(client):
    chunks = list(generation.stream_with_cache(client, _kb(), "q"))
    assert chunks == ["Hello ", "world"]


def test_session_stats_accumulate(client):
    kb = _kb()
    results = [generation.answer_with_cache(client, kb, "q") for _ in range(3)]
    stats = summarize(results)
    assert stats.query_count == 3
    assert stats.total_savings > 0
    assert stats.total_cached_tokens == 15000


def test_session_stats_immutable_add():
    s0 = SessionStats()
    s1 = s0.add(_dummy_result())
    assert s0.query_count == 0  # original unchanged
    assert s1.query_count == 1


def _dummy_result():
    from cag.models import CostBreakdown, QueryResult, TokenUsage
    return QueryResult(
        answer="x",
        usage=TokenUsage(cached_tokens=10, output_tokens=5),
        cost=CostBreakdown(total_cost=0.001, cost_without_cache=0.01),
        latency_ms=1.0, used_cache=True, model="gemini-2.5-flash",
    )
