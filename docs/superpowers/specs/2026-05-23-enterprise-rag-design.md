# EnterpriseRAG Design Spec

> 企业级 RAG 知识库问答系统 — 设计文档
> 创建日期: 2026-05-23

## Overview

基于 FastAPI + PostgreSQL + Chroma + LangChain + DeepSeek API 的检索增强生成问答系统。支持多用户认证、文档管理、多轮对话记忆、语义检索与答案溯源。

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.14 | AI ecosystem maturity |
| Backend | FastAPI | REST API, auto docs, async support |
| Database | PostgreSQL | Enterprise-grade, user/doc/message storage |
| Vector DB | Chroma | Lightweight, sufficient for dev |
| Framework | LangChain 0.3+ | Standardized RAG orchestration |
| Embedding | BAAI/bge-large-zh-v1.5 | SOTA Chinese embedding |
| Reranker | BAAI/bge-reranker-v2-m3 | Precision boost for retrieval |
| LLM | DeepSeek API (external) | Low cost, fast response |
| Auth | JWT (python-jose) | Stateless auth, standard practice |
| UI | Vue 3 + Vite | SPA, component-based, production-grade |
| Document Parse | PyPDF2 + python-docx + txt | Multi-format support |
| Chunking | RecursiveCharacterTextSplitter (512/128) | Balance completeness & granularity |
| Deployment | Docker Compose | Containerized, easy setup |

## Architecture

```
┌───────────────┐     HTTP/JWT    ┌──────────────────────────────────┐
│   Vue 3 SPA   │ ─────────────→  │        FastAPI Backend           │
│  (frontend/)  │ ←─────────────  │                                │
└───────────────┘    JSON API      │  ┌─────────┐  ┌──────────────┐  │
                                    │  │ Auth    │  │ Document     │  │
                                    │  │ Module  │  │ Ingestion    │  │
                                    │  └────┬────┘  └──────┬───────┘  │
                                    │       │              │          │
                                    │  ┌────▼────┐  ┌──────▼───────┐  │
                                    │  │ QA      │  │ Vector Store │  │
                                    │  │ Chain   │  │ (Chroma)     │  │
                                    │  └────┬────┘  └──────────────┘  │
                                    │       │                          │
                                    │  ┌────▼────┐                    │
                                    │  │ Memory  │                    │
                                    │  │ Manager │                    │
                                    │  └─────────┘                    │
                                    └────────┬─────────────────────────┘
                                              │
                    ┌──────────────────────────┼─────────────────┐
                    │            ┌─────────────▼───────────┐      │
                    │            │      PostgreSQL         │      │
                    │            │  • users                │      │
                    │            │  • documents            │      │
                    │            │  • conversations        │      │
                    │            │  • messages             │      │
                    │            └─────────────────────────┘      │
                    │         External Services                   │
                    │  ┌──────────────┐  ┌──────────────────┐    │
                    │  │ DeepSeek API │  │ BGE Embedding    │    │
                    │  │ (LLM)       │  │ + Reranker (local│    │
                    │  └──────────────┘  └──────────────────┘    │
                    └────────────────────────────────────────────┘
```

### Data Flow

**Ingestion**: Upload → Parse (PDF/MD/TXT) → Recursive Chunk (512/128) → BGE Embedding → Chroma (with metadata: filename, chunk_index, page)

**QA**: Question → Load ConversationSummaryMemory → Rewrite query (resolve anaphora) → BGE Embedding → Chroma Top-20 → BGE Reranker Top-5 → Build Prompt (System + Memory Summary + Context chunks + Question) → DeepSeek API → Parse answer + sources → Save to Memory → Return `{answer, sources[]}`

## Data Models

### PostgreSQL (SQLAlchemy ORM)

**users**: id (UUID PK), username (unique), hashed_password, role (admin/user), created_at
**documents**: id (UUID PK), user_id (FK), filename, file_type, status (processing/ready/failed), chunk_count, created_at
**conversations**: id (UUID PK), user_id (FK), title, created_at, updated_at
**messages**: id (UUID PK), conversation_id (FK), role (user/assistant), content, sources (JSON), created_at

### Chroma Collections

**doc_chunks**: id (doc_id + chunk_index), embedding, metadata (filename, chunk_index, page_number, text_content)

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/register` | POST | No | Register user |
| `/api/auth/login` | POST | No | Login → JWT token |
| `/api/documents` | GET | JWT | List user's documents |
| `/api/documents/upload` | POST | JWT | Upload & ingest document |
| `/api/documents/{id}` | DELETE | JWT | Delete document |
| `/api/documents/{id}/status` | GET | JWT | Check ingestion status |
| `/api/qa/ask` | POST | JWT | Ask question (with conversation_id) |
| `/api/conversations` | GET | JWT | List conversations |
| `/api/conversations/{id}` | GET | JWT | Get conversation messages |
| `/api/conversations/{id}` | DELETE | JWT | Delete conversation |

## RAG Pipeline Detail

### Ingestion
1. Accept file upload (PDF/MD/TXT/DOCX)
2. Parse using PyPDF2 / python-docx / built-in txt reader
3. RecursiveCharacterTextSplitter (chunk_size=512, overlap=128)
4. BAAI/bge-large-zh-v1.5 → vector for each chunk
5. Store in Chroma with metadata
6. Update document status in PostgreSQL

### Retrieval + Generation
1. User query + conversation_id → load memory summary
2. Rewrite query with context (LangChain prompt template)
3. Embed query via BGE model
4. Chroma similarity search (top_k=20)
5. BGE Reranker score all 20 → keep top 5
6. Build prompt:
   - System: role definition
   - Memory: conversation summary
   - Context: chunk text with `【来源: filename】` markers
   - Question: user query
7. Call DeepSeek API (temperature=0.1)
8. Parse response for `【来源: ...】` markers → structured sources list
9. Save to ConversationSummaryMemory
10. Save message pair to PostgreSQL
11. Return `{answer, sources[{filename, chunk_text, score}], conversation_id}`

### Multi-turn Memory
- LangChain ConversationSummaryMemory
- Each turn compresses/updates summary
- Summary injected into next query prompt
- Separate memory instance per conversation_id

## Project Structure

```
EnterpriseRAG/
├── frontend/                      # Vue 3 + Vite SPA
├── api/                          # FastAPI backend
│   ├── __init__.py
│   ├── main.py                   # FastAPI app + router registration
│   ├── auth.py                   # Register/login endpoints
│   ├── documents.py              # Document CRUD endpoints
│   └── qa.py                     # QA endpoints
├── core/                         # Core utilities
│   ├── __init__.py
│   ├── config.py                 # Config (DB URL, API keys, model paths)
│   ├── database.py               # PostgreSQL connection (SQLAlchemy)
│   ├── models.py                 # SQLAlchemy ORM models
│   └── schemas.py                # Pydantic schemas
├── rag/                          # RAG engine
│   ├── __init__.py
│   ├── document_loader.py        # Parse + chunk
│   ├── vector_store.py           # Chroma wrapper
│   ├── reranker.py               # BGE Reranker
│   ├── qa_chain.py               # Prompt + LLM call + source parsing
│   └── memory.py                 # ConversationSummaryMemory wrapper
├── requirements.txt
├── Dockerfile
├── docker-compose.yml            # FastAPI + PostgreSQL + nginx frontend
└── tests/
    ├── __init__.py
    ├── test_auth.py
    ├── test_ingestion.py
    ├── test_retrieval.py
    └── test_qa.py
```

## Error Handling

- API retry: tenacity with exponential backoff (for DeepSeek API)
- Invalid file type: return 400 with supported format list
- Auth failure: 401 with clear message
- Ingestion failure: 500, document status set to "failed" with error log
- LLM timeout: 504, prompt user to retry

## Performance Targets

- Recall@5 ≥ 85% (target 92% with Reranker)
- End-to-end latency ≤ 3s
- Rerank overhead ≤ 300ms (for 20 candidates)
- Single machine support: 100+ documents (~100K words)

## Implementation Order

| Phase | Content | Deliverable |
|-------|---------|-------------|
| 1. Infrastructure | FastAPI boilerplate, PostgreSQL setup, SQLAlchemy models, Docker Compose | Running API + DB |
| 2. Auth System | Register/login, JWT middleware, password hashing | Auth complete |
| 3. Document Ingestion | Parse/chunk/embed → Chroma, status tracking | document_loader + vector_store |
| 4. Retrieval + Rerank | Chroma search → BGE Reranker pipeline | Retrieval module, recall comparison |
| 5. QA Chain | Prompt build → DeepSeek → source parsing | qa_chain.py |
| 6. Multi-turn Memory | ConversationSummaryMemory integration | Multi-turn support |
| 7. Vue 3 Frontend | Login, document management, chat interface | frontend/ SPA |
| 8. Tuning + Docs | Chunk size / top_k / temperature tuning, README, demo video | Complete GitHub repo |

## Design Decisions

1. **FastAPI as separate backend** (not frontend-coupled): Provides REST API for external consumption, clean separation of concerns, higher resume value
2. **PostgreSQL over SQLite**: Enterprise-grade, concurrent access, migration path to production
3. **JWT stateless auth**: No session storage, standard REST practice, easy to scale
4. **Window + Summary memory**: Balances context retention vs token cost; summary survives long conversations
5. **Local BGE models** (not API): One-time download, no per-query embedding cost, lower latency
6. **Docker Compose**: One-command setup, consistent environment, demonstrates containerization skill
