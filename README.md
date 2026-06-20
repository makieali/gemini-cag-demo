# ⚡ Gemini CAG Demo

> A small, working demo of **Cache-Augmented Generation (CAG)** with the Google Gemini API — load your documents into a context cache once, then ask unlimited questions where the document tokens are billed at a **~90% discount**.

CAG is the cache-first cousin of RAG. Instead of chunking documents, embedding them, and retrieving fragments per query, CAG loads the **whole knowledge base into the model's context cache once** and reuses it on every call. For knowledge bases that fit in Gemini's long context window, this is simpler, has no retrieval step to get wrong, and is dramatically cheaper on repeated queries.

This app shows it end to end: upload documents → build a real Gemini context cache → ask questions → watch the cumulative cost savings add up. A **Compare mode** runs each question both with and without the cache so you can see the cost and latency difference live.

---

## RAG vs CAG, in one table

| | **RAG** (Retrieval-Augmented Generation) | **CAG** (Cache-Augmented Generation) |
|---|---|---|
| Knowledge prep | Chunk → embed → store in a vector DB | Upload files → create one context cache |
| Per-query work | Embed query → vector search → stitch context | Reference the cache by name |
| Moving parts | Embedder, vector DB, chunker, reranker | Just the model + a cache handle |
| Failure mode | Retrieval misses the relevant chunk | Knowledge base must fit the context window |
| Cost driver | Re-sends retrieved chunks each call | Cached tokens billed at a deep discount |
| Best when | Corpus is huge / changes constantly | Corpus is bounded and queried repeatedly |

CAG isn't a universal replacement for RAG — it shines when a **bounded** knowledge base (a contract, a manual, a codebase, a research bundle) is queried **many times**.

---

## How the caching actually works

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
                     │  )                                           │
                     │  → document tokens reused at ~90% off        │
                     └──────────────────────────────────────────────┘
```

Only the **question** is billed as fresh input on each call; the documents come from the cache. The app reads `usage_metadata.cached_content_token_count` from each response to compute exactly what you saved versus re-sending the documents.

---

## Features

- 🧠 **True context caching** — uses `client.caches.create` + `cached_content`, not just a big prompt.
- 💰 **Live savings dashboard** — cumulative cost, cached tokens, and % saved vs no-cache across the session.
- ⚖️ **Compare mode** — answers each question with *and* without the cache, side by side, with the cost/latency delta.
- ⏳ **Cache lifecycle** — TTL countdown, one-click extend, and delete to stop storage charges.
- 📄 **Multi-format uploads** — PDF, TXT, MD, DOCX, CSV, XLSX, PPTX, JSON (validated server-side).
- 🔌 **Official `google-genai` SDK**, model configurable via env (`gemini-2.5-flash` by default).
- ✅ **Tested** — 27 unit/integration tests, ~93% coverage on the core package, SDK fully mocked.

---

## Quickstart

```bash
git clone https://github.com/makieali/gemini-cag-demo.git
cd gemini-cag-demo

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set GEMINI_API_KEY (get one at https://aistudio.google.com/apikey)

python app.py
# open http://localhost:5069
```

### Docker

```bash
cp .env.example .env   # set GEMINI_API_KEY
docker compose up --build
```

---

## Configuration

All settings come from the environment (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | **Required.** Your Gemini API key. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Any caching-capable model. |
| `CACHE_TTL_SECONDS` | `3600` | How long a context cache lives. |
| `SECRET_KEY` | dev key | Flask session secret — set a real one in prod. |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode. |
| `MAX_CONTENT_LENGTH_MB` | `32` | Max upload size. |

---

## Project layout

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

Run the tests:

```bash
pip install -r requirements.txt
pytest
```

---

## Notes & caveats

- **Pricing is approximate.** Rates live in `cag/cost.py` and may lag the official [Gemini pricing](https://ai.google.dev/pricing). The dashboard is for illustrating *relative* savings — verify absolute numbers yourself.
- **Minimum cache size.** Gemini requires ~2,048 tokens of content before a cache can be created; very small documents can't be cached.
- **State is in-memory.** Knowledge bases are stored per-session in process memory (`cag/store.py`). For multi-process or production use, back it with Redis or a database — the rest of the app only touches the small `SessionStore` interface.
- **Context caching incurs a storage cost** per hour the cache lives. Delete caches you're done with (the UI does this for you).

---

## License

[MIT](./LICENSE) © 2026 Muhammad Ali

Built to demonstrate Gemini's [context caching](https://ai.google.dev/gemini-api/docs/caching) API.
