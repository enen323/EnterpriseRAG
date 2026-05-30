# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Python venv
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run API (FastAPI dev server)
uvicorn api.main:app --reload          # http://localhost:8000
# Frontend (Vue 3 + Vite)
cd frontend && npm install && npm run dev   # http://localhost:3000
cd frontend && npm run build                # production build

# Docker full stack
docker compose up -d

# Tests — all
pytest tests/ -v
# Tests — single file
pytest tests/test_auth.py -v
pytest tests/test_qa.py -v -k "test_parse_sources"

# DB migration
psql -U rag_user -d enterprise_rag -f docs/migration_v2.sql
```

## Architecture

Three-layer app: **FastAPI backend** → **PostgreSQL + Chroma** → **Vue 3 SPA**.

### Layer 1: API (`api/`)

FastAPI routers, all under `/api/*`. JWT auth via `HTTPBearer` middleware (`api/deps.py`). Each endpoint injects `current_user` + `db` session.

| Router | Prefix | Auth | Key endpoints |
|--------|--------|------|--------------|
| `auth.py` | `/api/auth` | No for register/login | register, login, me |
| `documents.py` | `/api/documents` | Yes | upload, list, delete, status, preview, batch upload, category filter |
| `qa.py` | `/api/qa` | Yes | ask (non-streaming), ask/stream (SSE), feedback |
| `conversations.py` | `/api/conversations` | Yes | list, get messages, delete |
| `admin.py` | `/api/admin` | Yes (admin) | users list, docs list, stats, delete user |
| `categories.py` | `/api/categories` | Yes | CRUD categories |

Upload flow: write file to temp → persist copy to `storage/` for preview → `load_document()` → `split_documents()` → `add_documents()` to Chroma → update DB status.

### Layer 2: Core (`core/`) + RAG Engine (`rag/`)

**`core/config.py`** — Pydantic `Settings`, reads `.env`. Includes DB, JWT, DeepSeek, Embedding, Chroma, Retrieval params, diversity lambda, storage path, streaming tokens. Enforces `DEEPSEEK_API_KEY` at startup.

**`core/database.py`** — Async SQLAlchemy with `asyncpg`. `async_session_factory` + `get_db()` dependency. `init_db()` runs `create_all` on startup (no Alembic needed for dev).

**`core/models.py`** — 6 tables: `users` (UUID PK, bcrypt hashed password, role: admin/user), `documents` (user-scoped, status enum, optional `storage_path` for preview, optional `category_id` FK), `conversations` (user-scoped), `messages` (role: user/assistant, JSON sources), `message_feedback` (message_id+user_id unique, up/down + optional comment), `categories` (user-scoped, name unique per user).

**RAG pipeline** (`rag/`):
1. `document_loader.py` — Parse PDF/MD/TXT/DOCX per type, return `List[LCDocument]`. Split via `RecursiveCharacterTextSplitter` (chunk_size=512, overlap=128).
2. `vector_store.py` — Chroma + BGE Embedding (`bge-large-zh-v1.5`) with query instruction prepended. Functions: `add_documents`, `delete_document_chunks`, `search_documents` (user-filtered).
3. `reranker.py` — BGE Reranker (`bge-reranker-v2-m3`). Lazy-loaded singleton. Two modes: `rerank` (baseline) and `rerank_with_diversity` (greedy selection with cosine similarity penalty, default). Top-20 → diversity-rerank → Top-5.
4. `qa_chain.py` — Formats context + memory summary into system prompt, calls DeepSeek via OpenAI SDK. `tenacity` retry (3 attempts, exponential backoff). Parses `【来源: filename】` citations from output. Non-streaming path appends follow-up prompt for inline Q: generation.
5. `memory.py` — `ConversationMemory` class. Compresses last 3 conversation turns into summary using DeepSeek. Falls back to concatenation on LLM error.
6. `streaming.py` — SSE event formatting + async generator for DeepSeek stream. Yields `token` events during streaming, `done` event on completion, `error` on failure. Follow-up questions generated via separate lightweight LLM call post-stream.

Full retrieve path: `search_documents(question, filter={user_id})` → `rerank_with_diversity(question, results)` → `ask_question(question, reranked, memory_summary)`.

Streaming path: same retrieve → `generate_stream(question, reranked, memory_summary)` yields SSE tokens → post-stream: parse sources, generate follow-ups, persist messages, yield metadata event.

### Layer 3: Frontend (`frontend/`)

Vue 3 + TypeScript + Vite + Pinia + Vue Router.

- `vite.config.ts` proxies `/api` → `localhost:8000`
- `src/api/index.ts` — Typed fetch client, localStorage JWT management, SSE streaming via ReadableStream
- `src/stores/auth.ts` — Pinia store: login, register, loadUser, logout
- `src/router/index.ts` — Routes: `/login`, `/chat` (requiresAuth guard), `/admin` (requiresAuth)
- `src/views/` — `LoginView.vue` (login/register tabs), `ChatView.vue` (sidebar + message area, streaming support), `AdminView.vue` (admin panel)
- `src/components/` — `ChatMessage.vue` (sources toggle, feedback thumbs up/down, follow-up chips), `DocumentList.vue` (upload/list/delete/preview/batch, category filter), `ConversationList.vue`, `DocPreview.vue` (modal preview), `CategorySelector.vue`

Chat data flow (streaming): user types → optimistic message insert → `qaApi.askStream()` SSE → progressively update message bubble per token → on metadata: replace temp messages with real ones.

### Data flow

```
Upload:  [file] → temp → storage/ copy (preview) → load_document() → split_documents() → Chroma add_documents() → DB status=ready
Ask:     [question] → search_documents(filter=user_id, top_k=20) → rerank_with_diversity(top_k=5) → 
         format_context() + memory_summary → DeepSeek API → parse_sources → save messages → return
Stream:  [question] → same retrieve/rerank → SSE(event_stream) → DeepSeek stream=TRUE → token events → post-stream: parse sources, generate follow-ups, persist → metadata event
```

User-scoped: Chroma chunks tagged with `user_id`; all document/conversation queries filter by `current_user.id`.

### Tests (`tests/`)

| File | Scope | Pattern |
|------|-------|---------|
| `conftest.py` | Shared fixtures | `db_session`, `async_client`, `auth_headers` via SQLite in-memory |
| `test_auth.py` | Auth endpoints | AsyncClient with SQLite in-memory DB override |
| `test_ingestion.py` | Doc parsing/chunking | tmp_path fixtures |
| `test_retrieval.py` | Search + rerank + diversity | Mocked embedding model, numpy-based mock |
| `test_memory.py` | ConversationMemory | Async tests, real LLM call for first turn |
| `test_qa.py` | Context format, source parsing, feedback, follow-ups | No LLM needed |

All tests use `pytest-asyncio` with `Mode.STRICT`.

### Key config (from `.env`)

```
DEEPSEEK_API_KEY=required
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DB_HOST=192.168.100.128  (or localhost via Docker)
JWT_SECRET=change-in-production
```

China HF mirror set automatically in `core/config.py` via `HF_ENDPOINT=https://hf-mirror.com`.

### Docker

`docker-compose.yml` runs: API (uvicorn), PostgreSQL 16, nginx serving frontend dist. Chroma persistence on named volume.

## Dev notes

- Python 3.14 native types required (no `from typing import List` etc. — use `list`, `dict`).
- All async: FastAPI + asyncpg + async SQLAlchemy.
- Tests use `pytest-asyncio`; must mark `@pytest.mark.asyncio` or use `pytest_asyncio.fixture`.
- Chroma is file-based (persist dir `chroma_db/`). No separate server.
- Frontend talks to API through Vite proxy in dev, nginx reverse proxy in production.
- New DB tables since v1: `message_feedback`, `categories`. Existing `documents` table has new nullable columns `storage_path` and `category_id`. Run `docs/migration_v2.sql` to migrate existing DB.
- Streaming SSE frontend uses `ReadableStream` with manual SSE line parsing (no EventSource dependency).
- Batch upload supports `.zip` archives with automatic extraction and per-file ingestion.
- Non-streaming `/ask` generates follow-up questions via prompt injection (same LLM call). Streaming `/ask/stream` uses separate lightweight LLM call post-stream.
