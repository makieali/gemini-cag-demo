<div align="center">

# ⚡ Gemini CAG Demo

### Cache-Augmented Generation with the Google Gemini API

**Load your documents into a context cache *once*, then ask unlimited questions where the document tokens are billed at a ~90% discount.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-27%20passing-brightgreen.svg)](#-testing)
[![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen.svg)](#-testing)
[![Gemini](https://img.shields.io/badge/Gemini-context%20caching-8E75FF.svg)](https://ai.google.dev/gemini-api/docs/caching)

</div>

---

CAG is the cache-first cousin of RAG. Instead of chunking documents, embedding them, and retrieving fragments per query, CAG loads the **whole knowledge base into the model's context cache once** and reuses it on every call. For knowledge bases that fit in Gemini's long context window, this is simpler (no retrieval step to get wrong) and dramatically cheaper on repeated queries.

This app shows it end to end: **upload documents → build a real Gemini context cache → ask questions → watch the savings add up.** A **Compare mode** runs each question both with and without the cache so you can see the cost and latency difference live.

## Contents

- [See it in action](#-see-it-in-action)
- [RAG vs CAG](#-rag-vs-cag-in-one-table)
- [How the caching actually works](#-how-the-caching-actually-works)
- [Features](#-features)
- [Quickstart](#-quickstart-60-seconds)
- [API reference](#-api-reference)
- [Configuration](#-configuration)
- [Project layout](#-project-layout)
- [Testing](#-testing)
- [Notes & caveats](#-notes--caveats)

## 🎬 See it in action

```
┌─ Gemini CAG ──────────────┐  ┌─ Compare mode: CAG vs full-context ──────────────┐
│ Knowledge base            │  │  ⚡ CAG 77% cheaper · 1.8× faster                │
│  ▸ report.pdf  ✓ cached   │  ├──────────────────────┬───────────────────────────┤
│  8,123 tokens   59:41 ⏳  │  │ ⚡ CAG (cached)       │ 📦 Full-context (no cache)│
│                           │  │ The report covers…   │ The report covers…        │
│ Cumulative savings        │  │ 🧠 8,000 cached      │ ✏️ 8,200 fresh            │
│   $0.004320               │  │ $0.000650            │ $0.002810                 │
│   77% saved vs no-cache   │  └──────────────────────┴───────────────────────────┘
└───────────────────────────┘
```

> 📸 **Maintainer tip:** drop a real screenshot or GIF at `docs/demo.png` and replace this block — a visual of the savings dashboard + compare mode makes the strongest first impression.

## 📊 RAG vs CAG, in one table

| | **RAG** (Retrieval-Augmented Generation) | **CAG** (Cache-Augmented Generation) |
|---|---|---|
| Knowledge prep | Chunk → embed → store in a vector DB | Upload files → create one context cache |
| Per-query work | Embed query → vector search → stitch context | Reference the cache by name |
| Moving parts | Embedder, vector DB, chunker, reranker | Just the model + a cache handle |
| Failure mode | Retrieval misses the relevant chunk | Knowledge base must fit the context window |
| Cost driver | Re-sends retrieved chunks each call | Cached tokens billed at a deep discount |
| Best when | Corpus is huge / changes constantly | Corpus is bounded and queried repeatedly |

CAG isn't a universal replacement for RAG — it shines when a **bounded** knowledge base (a contract, a manual, a codebase, a research bundle) is queried **many times**.

## 🔧 How the caching actually works

```
                     ┌──────────────────────────────────────────────┐
  1. Upload files    │  client.files.upload(...)  → Gemini Files API │
                     └──────────────────────────────────────────────┘
                                       │
                     ┌──────────────────────────────────────────────┐
  2. Build cache     │  client.caches.create(                       │
     (ONCE)          │      model, contents=[files], ttl="3600s")   │
                     │  → cachedContents/abc123   (KV state stored)  │
                     └──────────────────────────────────────────────┘
                                       │
                     ┌──────────────────────────────────────────────┐
  3. Ask (N times)   │  client.models.generate_content(             │
                     │      contents=question,                      │
                     │      config=GenerateContentConfig(           │
                     │          cached_content="cachedContents/abc")│
                     │  )  → document tokens reused at ~90% off      │
                     └──────────────────────────────────────────────┘
```

Only the **question** is billed as fresh input on each call; the documents come from the cache. The app reads `usage_metadata.cached_content_token_count` from each response to compute exactly what you saved versus re-sending the documents.

**A real run from this app** (8 KB document, default `gemini-2.5-flash`):

| | Cached prompt | Fresh prompt | Cost / query | vs no-cache |
|---|---|---|---|---|
| **CAG** | 8,000 tokens | 200 tokens | **$0.000650** | — |
| **Full-context** | 0 | 8,200 tokens | $0.002810 | |
| | | | | **↓ 77% cheaper** |

## ✨ Features

- 🧠 **True context caching** — uses `client.caches.create` + `cached_content`, not just a big prompt.
- 💰 **Live savings dashboard** — cumulative cost, cached tokens, and % saved vs no-cache across the session.
- ⚖️ **Compare mode** — answers each question with *and* without the cache, side by side, with the cost/latency delta.
- ⏳ **Cache lifecycle** — TTL countdown, one-click extend, and delete to stop storage charges.
- 📄 **Multi-format uploads** — PDF, TXT, MD, DOCX, CSV, XLSX, PPTX, JSON (validated server-side).
- 🔌 **Official `google-genai` SDK**, model configurable via env (`gemini-2.5-flash` by default).
- ✅ **Tested** — 27 unit/integration tests, ~93% coverage on the core package, SDK fully mocked.

## 🚀 Quickstart (60 seconds)

```bash
git clone https://github.com/makieali/gemini-cag-demo.git
cd gemini-cag-demo

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env → set GEMINI_API_KEY (free key at https://aistudio.google.com/apikey)

python app.py        # → http://localhost:5069
```

Then in the browser: **drop a document → "Build context cache" → ask away.** Toggle **Compare mode** to watch CAG beat full-context on every query.

### 🐳 Docker

```bash
cp .env.example .env   # set GEMINI_API_KEY
docker compose up --build
```

## 🔌 API reference

The browser UI is a thin layer over a small JSON API you can drive directly:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/kb` | Upload documents (`files[]`) and build a context cache |
| `GET` | `/api/kb` | Current knowledge-base status + TTL remaining |
| `POST` | `/api/kb/extend` | Extend the cache TTL |
| `DELETE` | `/api/kb` | Delete the cache (stops storage cost) |
| `POST` | `/api/ask` | Ask a question using the cache → answer + usage + cost |
| `POST` | `/api/compare` | Run the question with **and** without the cache |
| `GET` | `/api/stats` | Cumulative savings for the session |

<details>
<summary>Example: ask a question via curl</summary>

```bash
curl -s localhost:5069/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What does the contract say about termination?"}' | jq
# → { "answer": "...", "used_cache": true,
#     "usage": { "cached_tokens": 8000, "fresh_prompt_tokens": 200, ... },
#     "cost":  { "total_cost": 0.00065, "savings_pct": 76.9 }, ... }
```
</details>

## ⚙️ Configuration

All settings come from the environment (see [`.env.example`](./.env.example)):

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | **Required.** Your Gemini API key. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Any caching-capable model. |
| `CACHE_TTL_SECONDS` | `3600` | How long a context cache lives. |
| `SECRET_KEY` | dev key | Flask session secret — set a real one in prod. |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode. |
| `MAX_CONTENT_LENGTH_MB` | `32` | Max upload size. |

## 📁 Project layout

```
gemini-cag-demo/
├── app.py               # Flask routes (thin) — validate, delegate, serialize
├── config.py            # Env-based config
├── cag/                 # All Gemini/CAG logic (no Flask imports)
│   ├── cache_manager.py # create / get / extend / delete context caches
│   ├── generation.py    # cached vs full-context queries + streaming
│   ├── cost.py          # pricing + cached-vs-uncached cost accounting
│   ├── analytics.py     # cumulative session savings (immutable)
│   ├── files.py         # upload + validation
│   ├── store.py         # in-memory per-session KB store
│   └── models.py        # frozen dataclasses
├── templates/index.html
├── static/{css,js}
└── tests/               # pytest, SDK mocked
```

The `cag/` package has **no Flask dependency** — you can import it into a CLI, a notebook, or another framework.

## 🧪 Testing

```bash
pip install -r requirements.txt
pytest                       # 27 passed, ~93% coverage
```

Tests mock the Gemini SDK at the client boundary (`tests/conftest.py` injects a fake `google.genai`), so the suite runs **offline with no API key**. The full HTTP journey — build cache → ask → compare → stats → delete, plus validation failures — is covered in `tests/test_api.py`.

## 📝 Notes & caveats

- **Pricing is approximate.** Rates live in `cag/cost.py` and may lag the official [Gemini pricing](https://ai.google.dev/pricing). The dashboard illustrates *relative* savings — verify absolute numbers yourself.
- **Minimum cache size.** Gemini requires ~2,048 tokens of content before a cache can be created; very small documents can't be cached.
- **State is in-memory.** Knowledge bases are stored per-session in process memory (`cag/store.py`). For multi-process or production use, back it with Redis or a database — the rest of the app only touches the small `SessionStore` interface.
- **Caches incur a storage cost** per hour they live. Delete caches you're done with (the UI does this for you).

## 📄 License

[MIT](./LICENSE) © 2026 Muhammad Ali

<div align="center">
<sub>Built to demonstrate Gemini's <a href="https://ai.google.dev/gemini-api/docs/caching">context caching</a> API. ⭐ it if it helped.</sub>
</div>
