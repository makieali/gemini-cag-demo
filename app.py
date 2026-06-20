"""Flask app for the Gemini CAG demo.

Routes are thin: they validate input, delegate to the ``cag`` package, and
serialise immutable result objects to JSON. All Gemini-specific logic lives in
``cag/``.
"""
from __future__ import annotations

import os
import time
import uuid

from flask import Flask, jsonify, render_template, request, session
from werkzeug.utils import secure_filename

from cag import cache_manager, files as cag_files, generation
from cag.client import get_client
from cag.store import SessionStore
from config import Config


def create_app(store: SessionStore | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY
    app.store = store or SessionStore()

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

    def session_id() -> str:
        if "sid" not in session:
            session["sid"] = str(uuid.uuid4())
        return session["sid"]

    def client():
        return get_client(Config.require_api_key())

    def _serialize_result(result) -> dict:
        return {
            "answer": result.answer,
            "used_cache": result.used_cache,
            "model": result.model,
            "latency_ms": round(result.latency_ms, 1),
            "usage": {
                "prompt_tokens": result.usage.prompt_tokens,
                "cached_tokens": result.usage.cached_tokens,
                "fresh_prompt_tokens": result.usage.fresh_prompt_tokens,
                "output_tokens": result.usage.output_tokens,
                "total_tokens": result.usage.total_tokens,
            },
            "cost": {
                "total_cost": result.cost.total_cost,
                "cost_without_cache": result.cost.cost_without_cache,
                "savings": result.cost.savings,
                "savings_pct": round(result.cost.savings_pct, 1),
            },
        }

    @app.route("/")
    def index():
        return render_template("index.html", model=Config.GEMINI_MODEL)

    @app.post("/api/kb")
    def create_kb():
        """Upload documents and build a context cache (the knowledge base)."""
        try:
            Config.require_api_key()
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 500

        uploads = request.files.getlist("files[]")
        if not uploads or all(f.filename == "" for f in uploads):
            return jsonify({"error": "No files selected"}), 400

        sid = session_id()
        saved_paths: list[tuple[str, str]] = []
        uploaded = []
        try:
            for f in uploads:
                if f.filename == "":
                    continue
                cag_files.validate_filename(f.filename, Config.ALLOWED_EXTENSIONS)
                safe = secure_filename(f.filename)
                path = os.path.join(Config.UPLOAD_FOLDER, f"{sid}_{safe}")
                f.save(path)
                saved_paths.append((path, f.filename))

            for path, original in saved_paths:
                uploaded.append(cag_files.upload_file(client(), path, original))

            kb = cache_manager.create_cache(
                client(),
                model=Config.GEMINI_MODEL,
                files=tuple(uploaded),
                ttl_seconds=Config.CACHE_TTL_SECONDS,
                display_name=f"kb-{sid[:8]}",
            )
            app.store.set_kb(sid, kb)
        except cag_files.ValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except cache_manager.CacheTooSmallError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Failed to build knowledge base")
            return jsonify({"error": f"Failed to build cache: {exc}"}), 500
        finally:
            for path, _ in saved_paths:
                if os.path.exists(path):
                    os.remove(path)

        return jsonify({
            "message": f"Cached {len(uploaded)} document(s).",
            "cached_token_count": kb.cached_token_count,
            "expires_at": kb.expires_at,
            "files": [f.original_filename for f in kb.files],
            "model": kb.model,
        })

    @app.get("/api/kb")
    def kb_status():
        kb = app.store.get_kb(session_id())
        if not kb:
            return jsonify({"active": False})
        seconds_left = max(int(kb.expires_at - time.time()), 0) if kb.expires_at else None
        return jsonify({
            "active": True,
            "files": [f.original_filename for f in kb.files],
            "cached_token_count": kb.cached_token_count,
            "expires_at": kb.expires_at,
            "seconds_left": seconds_left,
            "model": kb.model,
        })

    @app.delete("/api/kb")
    def delete_kb():
        kb = app.store.clear(session_id())
        if kb:
            try:
                cache_manager.delete_cache(client(), kb.cache_name)
            except Exception:  # noqa: BLE001 - best effort cleanup
                app.logger.warning("Cache already gone: %s", kb.cache_name)
        return jsonify({"success": True})

    @app.post("/api/kb/extend")
    def extend_kb():
        kb = app.store.get_kb(session_id())
        if not kb:
            return jsonify({"error": "No active knowledge base"}), 400
        cache_manager.extend_ttl(client(), kb.cache_name, Config.CACHE_TTL_SECONDS)
        return jsonify({"success": True, "ttl_seconds": Config.CACHE_TTL_SECONDS})

    @app.post("/api/ask")
    def ask():
        sid = session_id()
        kb = app.store.get_kb(sid)
        if not kb:
            return jsonify({"error": "Upload documents first"}), 400
        question = (request.json or {}).get("question", "").strip()
        if not question:
            return jsonify({"error": "No question provided"}), 400
        try:
            result = generation.answer_with_cache(client(), kb, question)
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Query failed")
            return jsonify({"error": str(exc)}), 500
        stats = app.store.record_query(sid, result)
        payload = _serialize_result(result)
        payload["session_stats"] = _serialize_stats(stats)
        return jsonify(payload)

    @app.post("/api/compare")
    def compare():
        """Run the same question with and without the cache, side by side."""
        sid = session_id()
        kb = app.store.get_kb(sid)
        if not kb:
            return jsonify({"error": "Upload documents first"}), 400
        question = (request.json or {}).get("question", "").strip()
        if not question:
            return jsonify({"error": "No question provided"}), 400
        try:
            cached = generation.answer_with_cache(client(), kb, question)
            full = generation.answer_full_context(client(), kb, question)
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Compare failed")
            return jsonify({"error": str(exc)}), 500
        app.store.record_query(sid, cached)
        return jsonify({
            "cag": _serialize_result(cached),
            "full_context": _serialize_result(full),
        })

    @app.get("/api/stats")
    def stats():
        return jsonify(_serialize_stats(app.store.get_stats(session_id())))

    def _serialize_stats(s) -> dict:
        return {
            "query_count": s.query_count,
            "total_cost": s.total_cost,
            "total_cost_without_cache": s.total_cost_without_cache,
            "total_savings": s.total_savings,
            "savings_pct": round(s.savings_pct, 1),
            "total_cached_tokens": s.total_cached_tokens,
            "total_output_tokens": s.total_output_tokens,
        }

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=Config.PORT)
