# EnterpriseRAG Enhancement Design

**Date:** 2026-05-27
**Status:** Draft
**Scope:** Phase 1 enhancements — streaming/MMR, feedback, follow-up suggestions, document preview, batch upload, admin panel, document categories

---

## 1. Architecture Overview

Three-layer architecture unchanged (FastAPI → PostgreSQL + Chroma → Vue 3 SPA). Additions:

- **New tables:** `message_feedback`, `categories`, `category_documents`
- **New routes:** `/api/qa/ask/stream`, `/api/qa/feedback`, `/api/admin/*`, `/api/categories/*`
- **New modules:** `rag/streaming.py` (SSE helpers), `rag/diversity.py` (reranker diversity)
- **New frontend components:** `FeedbackButtons.vue`, `FollowUpChips.vue`, `DocPreview.vue`, `BatchUpload.vue`, `CategorySelector.vue`, `AdminView.vue`
- **Modified endpoints:** `POST /api/qa/ask` response adds `message_id`, `suggested_questions`

---

## 2. Streaming + MMR

### 2.1 Reranker with Diversity Penalty

**Problem:** Top-20 Chroma results often dominated by same document. Reranker alone doesn't penalize redundant chunks.

**Solution:** After reranker scoring, apply diversity penalty that discounts chunks similar to already-selected ones.

```
retrieve top-40 via Chroma → reranker scores all 40 → greedy selection with similarity penalty:
  score = reranker_score - λ * max_similarity(to_already_selected)
  pick highest-scoring chunk, repeat until top_k reached
```

**Implementation:** New function in `reranker.py` — `rerank_with_diversity(query, documents, top_k=5, diversity_lambda=0.3)`.

Similarity measured via embedding cosine distance between chunk embeddings (compute on-the-fly or cache from Chroma metadata).

**Config:**
```python
# config.py
RERANKER_DIVERSITY_LAMBDA: float = 0.3
```

### 2.2 Streaming Response (SSE)

**New endpoint:** `POST /api/qa/ask/stream`

Returns `text/event-stream` with format:
```
data: {"type": "token", "content": "基于"}
data: {"type": "token", "content": "提供的"}
data: {"type": "token", "content": "文档"}
data: {"type": "done", "answer": "完整答案...", "sources": [...], "conversation_id": "...", "message_id": "..."}
```

**Backend flow:**
1. Same pre-processing as `/ask` (resolve conversation, retrieve, rerank)
2. `client.chat.completions.create(stream=True, ...)` from DeepSeek
3. Yield each delta as SSE event
4. Non-streaming post-processing (save messages, generate follow-ups) happens after stream ends
5. Final `done` event contains complete response metadata

**Frontend:**
- Use `EventSource` or `fetch` with `ReadableStream`
- Accumulate tokens in buffer, update message bubble progressively
- Handle reconnection (in case of mid-stream disconnect, restart or show partial)

**API changes:**
```python
@router.post("/ask/stream")
async def ask_stream(req: QARequest, current_user, db):
    # ... pre-processing ...
    return StreamingResponse(
        _generate_stream(question, reranked, memory_summary, conv_id, current_user.id, db),
        media_type="text/event-stream",
    )
```

---

## 3. Answer Feedback

### 3.1 Database

```sql
CREATE TABLE message_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feedback VARCHAR(4) NOT NULL CHECK (feedback IN ('up', 'down')),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(message_id, user_id)
);
```

### 3.2 API

```
PATCH /api/qa/feedback
Request: { message_id: str, feedback: "up" | "down", comment?: str }
Response: { status: "ok" }
```

- Upsert behavior: same `(message_id, user_id)` updates existing record
- Requires auth (same user who owns the conversation)

### 3.3 Frontend

- `ChatMessage.vue` adds thumbs up/down buttons below assistant messages
- Selected state: filled icon, unselected: outline
- Downvote triggers optional textarea for explanation
- Feedback state persists across conversation reloads

---

## 4. Suggested Follow-Up Questions

### 4.1 Approach

Two paths depending on streaming vs non-streaming:

**Non-streaming (`POST /api/qa/ask`):** Generate 3 follow-ups in the same LLM call. Append to system prompt:

```
After your answer, generate 3 short follow-up questions the user might ask next.
Format each on a new line, prefixed with "Q:".
Keep each under 60 characters.
```

**Streaming (`POST /api/qa/ask/stream`):** After stream completes and full answer is accumulated server-side, make a second lightweight LLM call (low max_tokens=200, temperature=0.3) with prompt: "Based on this answer: '{answer}'. Generate 3 follow-up questions." This avoids polluting the streamed output with non-answer tokens.

### 4.2 Response Parsing

Modified `_parse_sources` in `qa_chain.py` also extracts `Q: ...` lines from answer as `suggested_questions`. Remove them from displayed answer.

### 4.3 API Changes

```python
class QAResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    conversation_id: str
    message_id: str  # NEW
    suggested_questions: list[str] | None = None  # NEW
```

### 4.4 Frontend

- Render suggested questions as clickable chips below assistant message
- Clicking a chip auto-fills input and sends
- Show only for latest assistant message in conversation

---

## 5. Document Preview

### 5.1 Scope

Text-only formats: `.txt`, `.md`, `.docx`. PDF excluded per scoping decision.

### 5.2 New Endpoint

```
GET /api/documents/{id}/preview
Response: { content: str, filename: str, file_type: str }
```

For `.txt`/`.md`: read original content. For `.docx`: extract text using `python-docx`.

**Note:** Current upload flow deletes temp file after ingestion. A `storage/` directory is needed:

- Upload saves file copy to `storage/documents/{user_id}/{doc_id}{ext}`
- Preview endpoint reads from storage
- Temp file deletion after ingestion still applies (docs already in Chroma)

### 5.3 Database Change

```python
# Document model adds:
storage_path: str | None = None  # path to stored file for preview
```

### 5.4 Frontend

- Preview button in `DocumentList.vue` (icon per doc item)
- Modal/side panel with `<pre>` for TXT, rendered markdown for MD, plain text for DOCX
- Close button and click-outside-to-dismiss

---

## 6. Batch Upload

### 6.1 Multi-File Upload

```
POST /api/documents/upload/batch
Content-Type: multipart/form-data
Body: files[] (multiple UploadFile)
Response: List[DocumentOut]
```

Backend iterates files, calls existing single-file ingestion for each. Partial failure handled: return success list + error messages for failed files.

### 6.2 ZIP Upload

Detect `.zip` extension or `application/zip` content type:

```python
import zipfile, tempfile
with zipfile.ZipFile(file.file) as zf:
    for name in zf.namelist():
        ext = os.path.splitext(name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(zf.read(name))
            # process tmp as single file upload
```

### 6.3 Frontend

- `<input type="file" multiple accept=".pdf,.md,.txt,.docx,.zip">`
- Visual progress: "Uploading file 3/7..."
- Success/failure summary after completion
- Drag-and-drop zone (optional, low priority)

---

## 7. Admin Panel

### 7.1 Admin Dependency

```python
# api/deps.py
async def require_admin(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
```

### 7.2 New Router: `api/admin.py`

```
GET  /api/admin/users        — list all users with doc/conversation counts
GET  /api/admin/documents    — list all documents across users
GET  /api/admin/stats        — summary: user count, doc count, msg count, storage usage
DELETE /api/admin/users/{id} — delete user + cascade
```

### 7.3 Frontend

- `AdminView.vue` — tabs for Users / Documents / Stats
- Simple table layout (no complex dashboards)
- Entry in sidebar only visible when `auth.user.role === 'admin'`
- Route guard `/admin` with role check

### 7.4 Stats Query

```python
SELECT 
    (SELECT count(*) FROM users) as user_count,
    (SELECT count(*) FROM documents) as doc_count,
    (SELECT count(*) FROM messages) as message_count,
    (SELECT count(*) FROM users WHERE created_at > NOW() - INTERVAL '7 days') as new_users_7d
```

---

## 8. Document Categories

### 8.1 Database

```sql
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, name)
);
```

```sql
-- Document model adds:
category_id UUID REFERENCES categories(id) ON DELETE SET NULL
```

### 8.2 API

```
GET    /api/categories           — list user's categories
POST   /api/categories           — create { name: str }
PUT    /api/categories/{id}      — rename { name: str }
DELETE /api/categories/{id}      — delete (documents uncategorized)
GET    /api/documents?category=X — filter by category name
```

### 8.3 Frontend

- `CategorySelector.vue` — dropdown in document list header
- Create/rename/delete via modal
- Active filter highlighted in sidebar

---

## 9. Implementation Order

| Phase | Features | Dependencies |
|-------|----------|-------------|
| P0 | Streaming + MMR, Message feedback, Follow-up suggestions | DB migration, config changes |
| P1 | Document preview, Batch upload | Storage directory setup |
| P2 | Admin panel, Categories | None |

---

## 10. Config Changes

```python
# core/config.py additions
RERANKER_DIVERSITY_LAMBDA: float = 0.3
STORAGE_DIR: str = str(Path(__file__).parent.parent / "storage")
```

---

## 11. Testing Strategy

| Feature | Test scope |
|---------|------------|
| Streaming | `test_qa.py` — stream endpoint returns proper SSE format |
| MMR diversity | `test_retrieval.py` — reranked results have lower duplicate ratio |
| Feedback | `test_qa.py` — create/update/delete feedback |
| Follow-ups | `test_qa.py` — parse suggested questions from response |
| Preview | `test_ingestion.py` — preview endpoint returns text content |
| Batch upload | `test_ingestion.py` — multi-file + zip processing |
| Admin | `test_auth.py` — admin-only endpoints reject non-admin |
| Categories | `test_ingestion.py` — CRUD + document filtering |

---

## 12. Open Questions

- Storage directory: use existing `chroma_db/` parent dir or separate `storage/`? → Separate `storage/`
- Feedback analytics: future consideration for RAG evaluation dashboard
- Category migration for existing documents: all start uncategorized (null)
