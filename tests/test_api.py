"""Integration tests for the Flask routes against the fake SDK."""
import io

import pytest

from cag import client as client_module
from cag.store import SessionStore
from config import Config


@pytest.fixture
def app(monkeypatch, tmp_path):
    import app as app_module

    monkeypatch.setattr(Config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    client_module.get_client.cache_clear()  # ensure FakeClient is built fresh

    flask_app = app_module.create_app(store=SessionStore())
    flask_app.config.update(TESTING=True, SECRET_KEY="test")
    return flask_app


@pytest.fixture
def http(app):
    return app.test_client()


def _build_kb(http):
    data = {"files[]": (io.BytesIO(b"some document text"), "doc.txt")}
    return http.post("/api/kb", data=data, content_type="multipart/form-data")


def test_index_renders(http):
    res = http.get("/")
    assert res.status_code == 200
    assert b"Cache-Augmented Generation" in res.data


def test_build_kb_then_ask(http):
    res = _build_kb(http)
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["cached_token_count"] == 5000

    res = http.post("/api/ask", json={"question": "What is this?"})
    body = res.get_json()
    assert res.status_code == 200
    assert body["used_cache"] is True
    assert body["usage"]["cached_tokens"] == 5000
    assert body["session_stats"]["query_count"] == 1
    assert body["cost"]["savings"] > 0


def test_ask_before_build_returns_400(http):
    res = http.post("/api/ask", json={"question": "hi"})
    assert res.status_code == 400


def test_reject_unsupported_file(http):
    data = {"files[]": (io.BytesIO(b"x"), "evil.exe")}
    res = http.post("/api/kb", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "Unsupported" in res.get_json()["error"]


def test_compare_returns_both_paths(http):
    _build_kb(http)
    res = http.post("/api/compare", json={"question": "summarize"})
    body = res.get_json()
    assert res.status_code == 200
    assert body["cag"]["used_cache"] is True
    assert body["full_context"]["used_cache"] is False
    assert body["cag"]["cost"]["total_cost"] < body["full_context"]["cost"]["total_cost"]


def test_kb_status_and_delete(http):
    _build_kb(http)
    assert http.get("/api/kb").get_json()["active"] is True
    assert http.delete("/api/kb").get_json()["success"] is True
    assert http.get("/api/kb").get_json()["active"] is False


def test_missing_api_key_returns_500(http, monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", None)
    data = {"files[]": (io.BytesIO(b"x"), "doc.txt")}
    res = http.post("/api/kb", data=data, content_type="multipart/form-data")
    assert res.status_code == 500
