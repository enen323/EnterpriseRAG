# EnterpriseRAG Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add streaming response w/ MMR diversity, answer feedback, follow-up suggestions, text preview, batch upload, admin panel, categories.

**Architecture:** Existing 3-layer untouched. Add 2 DB tables, 5 new API routes, 6 new frontend components. Each feature independent but sequenced for clean review.

**Tech Stack:** FastAPI SSE, DeepSeek streaming, Chroma MMR, Vue 3 composition API.

---

### Task 1: Config + DB Migration

**Files:**
- Modify: `core/config.py`
- Modify: `core/models.py`
- Modify: `core/schemas.py`

- [ ] **Step 1: Add config settings**

Add to `core/config.py`:
```python
# Diversity
RERANKER_DIVERSITY_LAMBDA: float = 0.3

# Storage
STORAGE_DIR: str = str(Path(__file__).parent.parent / "storage")

# Streaming
STREAMING_MAX_TOKENS: int = 4096

# Follow-up generation (stream path)
FOLLOWUP_MAX_TOKENS: int = 200
```

- [ ] **Step 2: Add MessageFeedback model**

Add to `core/models.py`:
```python
class MessageFeedback(Base):
    __tablename__ = "message_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    feedback: Mapped[str] = mapped_column(String(4), nullable=False)  # "up" or "down"
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("message_id", "user_id", name="uq_message_user_feedback"),)
```

- [ ] **Step 3: Add Message.storage_path and category_id columns**

Add to `Document` model in `core/models.py`:
```python
storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
```

- [ ] **Step 4: Add Category model**

Add to `core/models.py`:
```python
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_category_name"),)
    user = relationship("User", back_populates="categories")
    documents = relationship("Document", back_populates="category")
```

Add `User.categories` relationship in `User` model:
```python
categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
```

Add `Document.category` relationship in `Document` model:
```python
category = relationship("Category", back_populates="documents")
```

- [ ] **Step 5: Add new Pydantic schemas**

Add to `core/schemas.py`:
```python
# === Feedback ===
class FeedbackCreate(BaseModel):
    message_id: str
    feedback: str = ""  # "up" or "down"
    comment: str | None = None

    @field_validator("feedback")
    @classmethod
    def feedback_valid(cls, v: str) -> str:
        if v not in ("up", "down"):
            raise ValueError("feedback must be 'up' or 'down'")
        return v

class FeedbackOut(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    feedback: str
    comment: str | None
    created_at: datetime
    model_config = {"from_attributes": True}

# === Categories ===
class CategoryCreate(BaseModel):
    name: str

class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    model_config = {"from_attributes": True}

# === Admin ===
class UserAdminOut(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    doc_count: int
    conv_count: int
    created_at: datetime

class StatsOut(BaseModel):
    user_count: int
    doc_count: int
    message_count: int
    new_users_7d: int

# === Document Preview ===
class PreviewOut(BaseModel):
    content: str
    filename: str
    file_type: str
```

- [ ] **Step 6: Add message_id and suggested_questions to QAResponse**

Modify `QAResponse` in `core/schemas.py`:
```python
class QAResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    conversation_id: str
    message_id: str = ""         # NEW
    suggested_questions: list[str] | None = None  # NEW
```

- [ ] **Step 7: Add storage directory creation at startup**

Add to `core/config.py` after `settings` object:
```python
# Ensure storage directory exists at import time
storage_path = Path(settings.STORAGE_DIR)
storage_path.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 8: Init new tables**

Add to `core/database.py` `init_db()` or rely on SQLAlchemy `create_all` (already called in main.py lifespan). Since `create_all` adds new tables, no migration script needed for dev.

Add a comment in `main.py` lifespan noting tables auto-created.

---

### Task 2: Reranker with Diversity Penalty

**Files:**
- Modify: `rag/reranker.py`
- Test: `tests/test_retrieval.py`

- [ ] **Step 1: Add rerank_with_diversity function**

Add to `rag/reranker.py`:
```python
import numpy as np
from sentence_transformers import SentenceTransformer

_diversity_embedder = None

def _get_diversity_embedder():
    global _diversity_embedder
    if _diversity_embedder is None:
        from sentence_transformers import SentenceTransformer
        _diversity_embedder = SentenceTransformer(settings.EMBEDDING_MODEL, device=settings.EMBEDDING_DEVICE)
    return _diversity_embedder

def rerank_with_diversity(
    query: str,
    documents: List[Tuple[LCDocument, float]],
    top_k: int = settings.RERANKER_TOP_K,
    diversity_lambda: float = settings.RERANKER_DIVERSITY_LAMBDA,
) -> List[Tuple[LCDocument, float]]:
    """
    Rerank with diversity penalty.
    1. Score all docs with cross-encoder reranker
    2. Greedy selection: pick highest-scoring, then penalize remaining by similarity to selected set
    """
    if not documents:
        return []

    # Step 1: Cross-encoder scores
    reranker = _get_reranker()
    pairs = [(query, doc.page_content) for doc, _ in documents]
    scores = reranker.compute_score(pairs)
    scored = [(doc, float(score)) for (doc, _), score in zip(documents, scores)]

    # Step 2: Greedy diversity selection
    embedder = _get_diversity_embedder()
    texts = [doc.page_content for doc, _ in scored]
    embeddings = embedder.encode(texts, normalize_embeddings=True)

    selected_indices = []
    remaining = list(range(len(scored)))

    for _ in range(min(top_k, len(scored))):
        if not remaining:
            break

        best_idx = None
        best_score = -float("inf")

        for idx in remaining:
            rerank_score = scored[idx][1]

            # Diversity penalty: max cosine similarity to already selected
            penalty = 0.0
            if selected_indices:
                similarities = np.dot(embeddings[selected_indices], embeddings[idx])
                penalty = float(np.max(similarities))

            adjusted = rerank_score - diversity_lambda * penalty

            if adjusted > best_score:
                best_score = adjusted
                best_idx = idx

        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining.remove(best_idx)

    return [scored[i] for i in selected_indices]
```

- [ ] **Step 2: Update ask endpoint to use diversity rerank**

In `api/qa.py`, change `reranked = rerank(...)` to:
```python
from rag.reranker import rerank_with_diversity
reranked = rerank_with_diversity(req.question, raw_results)
```

- [ ] **Step 3: Write test**

Add to `tests/test_retrieval.py`:
```python
@pytest.mark.asyncio
async def test_rerank_diversity_reduces_duplicates():
    """rerank_with_diversity should select diverse chunks over similar ones."""
    from rag.reranker import rerank_with_diversity
    from langchain_core.documents import Document as LCDocument

    docs = [
        (LCDocument(page_content="Python is a programming language", metadata={"source": "a.md"}), 0.9),
        (LCDocument(page_content="Python supports OOP and functional programming", metadata={"source": "a.md"}), 0.85),
        (LCDocument(page_content="Java is a compiled language", metadata={"source": "b.md"}), 0.8),
    ]
    result = rerank_with_diversity("tell me about python", docs, top_k=2, diversity_lambda=0.5)
    assert len(result) == 2
    sources = [doc.metadata["source"] for doc, _ in result]
    assert "b.md" in sources  # diverse doc should be selected over similar ones
```

- [ ] **Step 4: Run test**

Run: `pytest tests/test_retrieval.py::test_rerank_diversity_reduces_duplicates -v`
Expected: PASS

---

### Task 3: Streaming SSE Endpoint

**Files:**
- Create: `rag/streaming.py`
- Modify: `rag/qa_chain.py`
- Modify: `api/qa.py`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/views/ChatView.vue`
- Test: `tests/test_qa.py`

- [ ] **Step 1: Create streaming helper module**

`rag/streaming.py`:
```python
import json
import logging
from typing import AsyncGenerator, Tuple, List

from langchain_core.documents import Document as LCDocument

logger = logging.getLogger(__name__)

def format_sse_event(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"

async def generate_stream(
    question: str,
    context_docs: List[Tuple[LCDocument, float]],
    memory_summary: str = "",
) -> AsyncGenerator[str, None]:
    """Generate SSE events for streaming LLM response."""
    from rag.qa_chain import _format_context, SYSTEM_PROMPT
    from core.config import settings
    from openai import AsyncOpenAI

    if not settings.DEEPSEEK_API_KEY:
        yield format_sse_event("error", {"message": "DEEPSEEK_API_KEY not configured"})
        return

    context = _format_context(context_docs)
    prompt = SYSTEM_PROMPT.format(context=context, memory_summary=memory_summary or "No previous conversation.")

    client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_API_BASE)
    stream = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.STREAMING_MAX_TOKENS,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": question},
        ],
        stream=True,
    )

    full_answer = []
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            full_answer.append(delta)
            yield format_sse_event("token", {"content": delta})

    yield format_sse_event("done", {"answer": "".join(full_answer)})
```

- [ ] **Step 2: Add ask_question helper returning raw answer**

Add to `rag/qa_chain.py`:
```python
# Expose _format_context and SYSTEM_PROMPT for streaming module
# (already module-level, just ensure they're importable)

def extract_suggested_questions(answer: str) -> Tuple[str, list[str]]:
    """Extract Q: prefixed follow-up questions from answer. Return (clean_answer, questions)."""
    lines = answer.split("\n")
    clean_lines = []
    questions = []
    for line in lines:
        if line.strip().startswith("Q:"):
            questions.append(line.strip()[2:].strip())
        else:
            clean_lines.append(line)
    return "\n".join(clean_lines).strip(), questions
```

- [ ] **Step 3: Add streaming ask endpoint**

Add to `api/qa.py`:
```python
from fastapi.responses import StreamingResponse
from rag.streaming import generate_stream, format_sse_event

@router.post("/ask/stream")
async def ask_stream(
    req: QARequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Resolve or create conversation (same as /ask)
    if req.conversation_id:
        conv_id = uuid.UUID(req.conversation_id)
        result = await db.execute(
            select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == current_user.id)
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(id=uuid.uuid4(), user_id=current_user.id, title=req.question[:50])
        db.add(conv)
        await db.commit()
        conv_id = conv.id

    # Save user message
    user_msg = Message(id=uuid.uuid4(), conversation_id=conv_id, role="user", content=req.question)
    db.add(user_msg)
    await db.commit()

    # Check docs
    doc_result = await db.execute(
        select(Document).where(Document.user_id == current_user.id, Document.status == DocumentStatus.READY)
    )
    if not doc_result.scalars().all():
        raise HTTPException(status_code=400, detail="No processed documents found.")

    # Retrieve + diversity rerank
    raw_results = search_documents(req.question, filter={"user_id": str(current_user.id)})
    reranked = rerank_with_diversity(req.question, raw_results)

    # Build source items
    source_items = []
    for doc, score in reranked:
        source_items.append(SourceItem(
            filename=doc.metadata.get("source", "unknown"),
            chunk_text=doc.page_content[:200],
            score=score,
        ))

    # Memory summary
    prev_result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    prev_messages = prev_result.scalars().all()

    from rag.memory import ConversationMemory
    memory = ConversationMemory()
    prev_pairs = []
    for i in range(0, len(prev_messages) - 1, 2):
        if i + 1 < len(prev_messages):
            prev_pairs.append((prev_messages[i].content, prev_messages[i + 1].content))
    for user_q, assistant_a in prev_pairs[-3:]:
        await memory.update_summary(user_q, assistant_a)
    memory_summary = memory.get_summary()

    async def event_stream():
        from rag.qa_chain import extract_suggested_questions
        from rag.memory import ConversationMemory
        from openai import AsyncOpenAI
        from core.config import settings

        # Collect full answer from stream
        full_answer_chunks = []
        async for event in generate_stream(req.question, reranked, memory_summary):
            yield event
            # Accumulate for post-processing
            import json
            if event.startswith("data: "):
                try:
                    data = json.loads(event[6:])
                    if data.get("type") == "token":
                        full_answer_chunks.append(data["content"])
                except json.JSONDecodeError:
                    pass

        full_answer = "".join(full_answer_chunks)

        # Parse sources from answer
        from rag.qa_chain import _parse_sources
        clean_answer, _ = _parse_sources(full_answer)

        # Generate follow-up questions (second lightweight call)
        suggested = []
        try:
            client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_API_BASE)
            resp = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                temperature=0.3,
                max_tokens=settings.FOLLOWUP_MAX_TOKENS,
                messages=[
                    {"role": "user", "content": f"Based on this Q&A:\nQ: {req.question}\nA: {clean_answer}\n\nGenerate 3 short follow-up questions (max 60 chars each). Prefix each with 'Q:'."}
                ],
            )
            raw = resp.choices[0].message.content or ""
            _, suggested = extract_suggested_questions(raw)
        except Exception as e:
            logger.warning(f"Follow-up generation failed: {e}")

        # Update memory
        mem = ConversationMemory()
        await mem.update_summary(req.question, clean_answer)

        # Save assistant message
        assistant_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="assistant",
            content=clean_answer,
            sources=[s.model_dump() for s in source_items],
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        # Send final metadata
        yield format_sse_event("metadata", {
            "conversation_id": str(conv_id),
            "message_id": str(assistant_msg.id),
            "sources": [s.model_dump() for s in source_items],
            "suggested_questions": suggested,
        })

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Update frontend API client**

Add to `frontend/src/api/index.ts`:
```typescript
// Streaming
async askStream(
  params: { question: string; conversation_id: string | null },
  onToken: (token: string) => void,
  onDone: (result: { conversation_id: string; message_id: string; sources: SourceItem[]; suggested_questions?: string[] }) => void,
  onError: (err: Error) => void,
): Promise<AbortController> {
  const token = getToken();
  const controller = new AbortController();

  const response = await fetch(`${BASE}/qa/ask/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(params),
    signal: controller.signal,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    onError(new Error(err.detail || 'Stream request failed'));
    return controller;
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const data = JSON.parse(line.slice(6));
        switch (data.type) {
          case 'token':
            onToken(data.content);
            break;
          case 'metadata':
            onDone(data);
            break;
          case 'error':
            onError(new Error(data.message));
            break;
        }
      } catch { /* skip malformed */ }
    }
  }

  return controller;
}
```

- [ ] **Step 5: Update ChatView.vue for streaming**

In `frontend/src/views/ChatView.vue`, modify `sendQuestion` to use streaming:

```typescript
import { ref } from 'vue'
// Add streaming message state
const streamingContent = ref('')
const streamingMsgId = ref('temp-stream-' + Date.now())

// In sendQuestion, when conversation has ready docs:
async function sendQuestion() {
  // ... validation ...
  
  // Add user message
  messages.value.push({ id: 'temp-' + Date.now(), role: 'user', content: q, sources: null, created_at: new Date().toISOString() })

  // Add placeholder for streamed response
  streamingContent.value = ''
  messages.value.push({
    id: streamingMsgId.value,
    role: 'assistant',
    content: '',
    sources: null as any,
    created_at: new Date().toISOString(),
  })

  loading.value = true
  try {
    await qaApi.askStream(
      { question: q, conversation_id: conversationId.value || null },
      // onToken
      (token) => {
        streamingContent.value += token
        // Update the placeholder message content reactively
        const idx = messages.value.findIndex(m => m.id === streamingMsgId.value)
        if (idx >= 0) messages.value[idx] = { ...messages.value[idx], content: streamingContent.value }
      },
      // onDone
      (result) => {
        // Replace temp messages with real ones
        messages.value = messages.value.filter(m => m.id !== streamingMsgId.value)
        messages.value.pop() // remove temp user msg
        messages.value.push(
          { id: 'user-' + Date.now(), role: 'user', content: q, sources: null, created_at: new Date().toISOString() },
          { id: 'assistant-' + Date.now(), role: 'assistant', content: streamingContent.value, sources: result.sources as SourceItem[], created_at: new Date().toISOString() }
        )
        conversationId.value = result.conversation_id
        convListRef.value?.load()
        scrollToBottom()
      },
      // onError
      (err) => {
        error.value = err.message
        messages.value = messages.value.filter(m => m.id !== streamingMsgId.value)
      }
    )
  } catch (e: any) {
    error.value = e.message || 'Stream failed'
    messages.value = messages.value.filter(m => m.id !== streamingMsgId.value)
  } finally {
    loading.value = false
    streamingContent.value = ''
  }
}
```

- [ ] **Step 6: Write test**

In `tests/test_qa.py`:
```python
@pytest.mark.asyncio
async def test_extract_suggested_questions():
    from rag.qa_chain import extract_suggested_questions

    answer = """Based on documents, Python is dynamically typed.

Q: What are Python's main data types?
Q: How does Python compare to Java?
Q: Is Python good for beginners?"""

    clean, questions = extract_suggested_questions(answer)
    assert "dynamically typed" in clean
    assert "Q:" not in clean
    assert len(questions) == 3
    assert "What are Python's main data types?" in questions
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_qa.py::test_extract_suggested_questions -v`
Expected: PASS

---

### Task 4: Answer Feedback

**Files:**
- Modify: `api/qa.py`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/components/ChatMessage.vue`
- Test: `tests/test_qa.py`

- [ ] **Step 1: Add feedback endpoint**

Add to `api/qa.py`:
```python
@router.patch("/feedback")
async def submit_feedback(
    req: FeedbackCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Verify message belongs to user's conversation
    msg_result = await db.execute(
        select(Message)
        .join(Conversation)
        .where(Message.id == uuid.UUID(req.message_id), Conversation.user_id == current_user.id)
    )
    msg = msg_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # Upsert feedback
    result = await db.execute(
        select(MessageFeedback).where(
            MessageFeedback.message_id == msg.id,
            MessageFeedback.user_id == current_user.id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.feedback = req.feedback
        existing.comment = req.comment
    else:
        fb = MessageFeedback(
            id=uuid.uuid4(),
            message_id=msg.id,
            user_id=current_user.id,
            feedback=req.feedback,
            comment=req.comment,
        )
        db.add(fb)

    await db.commit()
    return {"status": "ok"}
```

- [ ] **Step 2: Add message_id to non-streaming ask response**

In `api/qa.py` `/ask` endpoint, after saving assistant message add `await db.refresh(assistant_msg)` and include `message_id=str(assistant_msg.id)` in response.

- [ ] **Step 3: Update QAResponse return**

In `api/qa.py` `/ask` endpoint, change return to:
```python
return QAResponse(
    answer=answer,
    sources=source_items,
    conversation_id=str(conv_id),
    message_id=str(assistant_msg.id),
    suggested_questions=suggested or None,
)
```

- [ ] **Step 4: Add frontend API method**

In `frontend/src/api/index.ts`:
```typescript
async feedback(params: { message_id: string; feedback: string; comment?: string }): Promise<void> {
  const token = getToken();
  await fetch(`${BASE}/qa/feedback`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(params),
  });
}
```

- [ ] **Step 5: Add feedback buttons to ChatMessage**

In `frontend/src/components/ChatMessage.vue`, add after `sources` section:
```vue
<div v-if="message.role === 'assistant' && message.id" class="feedback">
  <button :class="['btn-feedback', { active: feedbackValue === 'up' }]" @click="vote('up')" title="有用">👍</button>
  <button :class="['btn-feedback', { active: feedbackValue === 'down' }]" @click="vote('down')" title="无用">👎</button>
  <div v-if="showCommentBox" class="comment-box">
    <textarea v-model="commentText" placeholder="补充说明（可选）" rows="2"></textarea>
    <button @click="submitFeedback">提交</button>
  </div>
</div>
```

Add script:
```typescript
import { ref } from 'vue'
import { qaApi } from '../api'

const props = defineProps<{ message: MessageOut }>()
const feedbackValue = ref<string | null>(null)
const showCommentBox = ref(false)
const commentText = ref('')

async function vote(type: string) {
  if (feedbackValue.value === type) {
    feedbackValue.value = null
  } else {
    feedbackValue.value = type
    if (type === 'down') {
      showCommentBox.value = true
    } else {
      await qaApi.feedback({ message_id: props.message.id as string, feedback: type })
    }
  }
}

async function submitFeedback() {
  await qaApi.feedback({
    message_id: props.message.id as string,
    feedback: feedbackValue.value || 'down',
    comment: commentText.value || undefined,
  })
  showCommentBox.value = false
  commentText.value = ''
}
```

- [ ] **Step 6: Write test**

In `tests/test_qa.py`:
```python
@pytest.mark.asyncio
async def test_feedback_upsert(async_client, auth_headers):
    """Test feedback create and update."""
    # First create a question to get a message
    # Then submit feedback
    response = await async_client.patch(
        "/api/qa/feedback",
        json={"message_id": "some-msg-id", "feedback": "up"},
        headers=auth_headers,
    )
    # This will fail if msg doesn't exist, which tests the validation path
    assert response.status_code == 404
```

---

### Task 5: Follow-Up Suggestions (Non-Streaming)

**Files:**
- Modify: `rag/qa_chain.py`
- Modify: `api/qa.py`
- Modify: `frontend/src/components/ChatMessage.vue`

- [ ] **Step 1: Add follow-up generation to system prompt**

Modify `SYSTEM_PROMPT` in `rag/qa_chain.py` — append to instructions:
```
6. After your answer, generate 3 short follow-up questions the user might ask next.
   Format each on a new line, prefixed with "Q:".
   Keep each under 60 characters.
```

- [ ] **Step 2: Modify ask_question to extract follow-ups**

In `rag/qa_chain.py`, modify `ask_question`:
```python
async def ask_question(
    question: str,
    context_docs: List[Tuple[LCDocument, float]],
    memory_summary: str = "",
) -> Tuple[str, list, list[str]]:  # (answer, sources, suggested_questions)
    """Call DeepSeek API with context."""
    # ... same setup ...
    answer = await _call_llm(prompt, question)
    answer, sources = _parse_sources(answer)
    from rag.qa_chain import extract_suggested_questions  # or use inline
    answer, suggested = extract_suggested_questions(answer)
    return answer, sources, suggested
```

Update all callers of `ask_question` (in api/qa.py) to unpack 3 values.

- [ ] **Step 3: Update /ask endpoint to return suggested questions**

In `api/qa.py`:
```python
answer, parsed_sources, suggested = await ask_question(req.question, reranked, memory_summary)
# ...
return QAResponse(
    answer=answer,
    sources=source_items,
    conversation_id=str(conv_id),
    message_id=str(assistant_msg.id),
    suggested_questions=suggested or None,
)
```

- [ ] **Step 4: Add follow-up chips to ChatMessage**

In `frontend/src/components/ChatMessage.vue`, add after feedback section:
```vue
<div v-if="message.suggested_questions && message.suggested_questions.length > 0" class="suggested">
  <span class="suggested-label">追问:</span>
  <button
    v-for="(q, i) in message.suggested_questions"
    :key="i"
    class="chip"
    @click="$emit('suggestClick', q)"
  >
    {{ q }}
  </button>
</div>
```

Add emit:
```typescript
defineEmits<{ suggestClick: [question: string] }>()
```

Update `MessageOut` type in frontend to include `suggested_questions?: string[]`.

- [ ] **Step 5: Handle chip click in ChatView**

In `frontend/src/views/ChatView.vue`, template:
```vue
<ChatMessage
  v-for="msg in messages"
  :key="msg.id"
  :message="msg"
  @suggest-click="(q: string) => { question = q; sendQuestion() }"
/>
```

---

### Task 6: Document Preview (Text Only)

**Files:**
- Modify: `api/documents.py`
- Create: `frontend/src/components/DocPreview.vue`
- Modify: `frontend/src/components/DocumentList.vue`
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 1: Add storage file persistence during upload**

In `api/documents.py`, modify `upload_document` to save file copy:
```python
import shutil
from pathlib import Path

# After getting tmp_path, copy to storage before processing
storage_dir = Path(settings.STORAGE_DIR) / str(current_user.id)
storage_dir.mkdir(parents=True, exist_ok=True)
storage_path = storage_dir / f"{doc_id}{ext}"
shutil.copy2(tmp_path, storage_path)
doc_record.storage_path = str(storage_path)
```

- [ ] **Step 2: Add preview endpoint**

In `api/documents.py`:
```python
@router.get("/{doc_id}/preview", response_model=PreviewOut)
async def preview_document(
    doc_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.file_type in (".md", ".txt"):
        content = Path(doc.storage_path).read_text(encoding="utf-8") if doc.storage_path else "File not available"
    elif doc.file_type == ".docx":
        from docx import Document as DocxDocument
        d = DocxDocument(doc.storage_path) if doc.storage_path else None
        content = "\n".join(p.text for p in d.paragraphs if p.text.strip()) if d else "File not available"
    else:
        raise HTTPException(status_code=400, detail="Preview not available for this file type")

    return PreviewOut(content=content, filename=doc.filename, file_type=doc.file_type)
```

- [ ] **Step 3: Add frontend API method**

In `frontend/src/api/index.ts`:
```typescript
async preview(id: string): Promise<{ content: string; filename: string; file_type: string }> {
  const token = getToken();
  const res = await fetch(`${BASE}/documents/${id}/preview`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}
```

- [ ] **Step 4: Create DocPreview component**

`frontend/src/components/DocPreview.vue`:
```vue
<template>
  <div v-if="visible" class="preview-overlay" @click.self="$emit('close')">
    <div class="preview-modal">
      <div class="preview-header">
        <span class="preview-title">{{ filename }}</span>
        <button class="preview-close" @click="$emit('close')">✕</button>
      </div>
      <div class="preview-body">
        <pre v-if="fileType === '.txt'" class="preview-text">{{ content }}</pre>
        <div v-else-if="fileType === '.md'" class="preview-markdown">{{ content }}</div>
        <div v-else class="preview-text">{{ content }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  content: string
  filename: string
  fileType: string
}>()
defineEmits<{ close: [] }>()
</script>

<style scoped>
.preview-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.preview-modal {
  background: #fff; border-radius: 12px; width: 80%; max-width: 800px;
  max-height: 80vh; display: flex; flex-direction: column; box-shadow: 0 4px 24px rgba(0,0,0,0.15);
}
.preview-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #eee;
}
.preview-title { font-weight: 600; font-size: 15px; }
.preview-close { background: none; border: none; font-size: 18px; cursor: pointer; color: #999; }
.preview-close:hover { color: #333; }
.preview-body {
  padding: 20px; overflow-y: auto; flex: 1;
}
.preview-text { white-space: pre-wrap; font-size: 13px; line-height: 1.6; }
.preview-markdown { font-size: 14px; line-height: 1.6; }
</style>
```

- [ ] **Step 5: Add preview button to DocumentList**

In `frontend/src/components/DocumentList.vue`, add preview icon + modal logic. Inside doc-item:
```vue
<button class="btn-icon" title="预览" @click="previewDoc(doc)">👁</button>
```

Add:
```vue
<DocPreview
  :visible="previewVisible"
  :content="previewContent"
  :filename="previewFilename"
  :file-type="previewFileType"
  @close="previewVisible = false"
/>
```

```typescript
import DocPreview from './DocPreview.vue'
const previewVisible = ref(false)
const previewContent = ref('')
const previewFilename = ref('')
const previewFileType = ref('')

async function previewDoc(doc: DocumentOut) {
  try {
    const res = await docApi.preview(doc.id)
    previewContent.value = res.content
    previewFilename.value = res.filename
    previewFileType.value = res.file_type
    previewVisible.value = true
  } catch (err: any) {
    alert(err.message || 'Preview failed')
  }
}
```

---

### Task 7: Batch Upload

**Files:**
- Modify: `api/documents.py`
- Modify: `frontend/src/components/DocumentList.vue`
- Modify: `frontend/src/api/index.ts`
- Test: `tests/test_ingestion.py`

- [ ] **Step 1: Add batch upload endpoint**

Add to `api/documents.py`:
```python
@router.post("/upload/batch", response_model=List[DocumentOut], status_code=status.HTTP_201_CREATED)
async def upload_documents_batch(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    files: List[UploadFile] = File(...),
):
    results = []
    for file in files:
        try:
            # Reuse single-upload logic inline
            ext = os.path.splitext(file.filename or "")[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue

            doc_id = uuid.uuid4()
            doc_record = Document(
                id=doc_id, user_id=current_user.id, filename=file.filename or "unknown",
                file_type=ext, status=DocumentStatus.PROCESSING,
            )
            db.add(doc_record)
            await db.flush()

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(await file.read())
                    tmp_path = tmp.name

                raw_docs = load_document(tmp_path)
                chunks = split_documents(raw_docs)
                chunk_count = add_documents(chunks, str(doc_id), user_id=str(current_user.id))

                doc_record.status = DocumentStatus.READY
                doc_record.chunk_count = chunk_count
            except Exception as e:
                doc_record.status = DocumentStatus.FAILED
                logger.error(f"Batch doc failed: {file.filename}: {e}")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            await db.refresh(doc_record)
            results.append(doc_record)
        except Exception as e:
            logger.error(f"Batch upload file error: {file.filename}: {e}")

    await db.commit()
    return results
```

- [ ] **Step 2: Add ZIP upload support**

In same endpoint, add ZIP detection:
```python
import zipfile
import io

async def _process_zip(file: UploadFile, current_user, db) -> list[Document]:
    results = []
    content = await file.read()
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for name in zf.namelist():
            ext = os.path.splitext(name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            # Process each file in zip
            doc_id = uuid.uuid4()
            doc_record = Document(...)
            # ... same upload logic using zf.read(name) as content ...
            results.append(doc_record)
    return results
```

Modify `upload_documents_batch` to detect zip and route accordingly:
```python
if ext == ".zip":
    results = await _process_zip(file, current_user, db)
else:
    # single file in batch list
```

- [ ] **Step 3: Add frontend batch upload UI**

In `frontend/src/components/DocumentList.vue`, modify upload button:
```vue
<label class="upload-btn">
  上传文档
  <input type="file" accept=".pdf,.md,.txt,.docx,.zip" multiple hidden @change="uploadFiles" />
</label>
```

Replace `uploadFile` with:
```typescript
async function uploadFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input?.files
  if (!files || files.length === 0) return
  uploading.value = true
  let count = 0
  for (const file of Array.from(files)) {
    try {
      if (file.name.endsWith('.zip')) {
        await docApi.upload(file) // single zip upload handled by batch endpoint
      } else {
        await docApi.upload(file) // single file
      }
      count++
    } catch (err: any) {
      alert(`${file.name} 上传失败: ${err.message}`)
    }
  }
  await load()
  uploading.value = false
  input.value = ''
}
```

Add to `frontend/src/api/index.ts`:
```typescript
async uploadBatch(files: File[]): Promise<DocumentOut[]> {
  const token = getToken();
  const form = new FormData();
  files.forEach(f => form.append('files', f));
  const res = await fetch(`${BASE}/documents/upload/batch`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}
```

- [ ] **Step 4: Write test**

In `tests/test_ingestion.py`:
```python
@pytest.mark.asyncio
async def test_batch_upload_rejects_invalid_files():
    """Batch upload should skip unsupported file types."""
    from api.documents import ALLOWED_EXTENSIONS
    assert ".pdf" in ALLOWED_EXTENSIONS
    assert ".zip" in ALLOWED_EXTENSIONS  # for zip batch
```

---

### Task 8: Admin Panel

**Files:**
- Create: `api/admin.py`
- Modify: `api/main.py`
- Modify: `api/deps.py`
- Create: `frontend/src/views/AdminView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/api/index.ts`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Add admin dependency**

In `api/deps.py`:
```python
async def require_admin(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
```

- [ ] **Step 2: Create admin router**

`api/admin.py`:
```python
import uuid
import logging
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import User, Document, Message, Conversation
from core.schemas import UserAdminOut, StatsOut, DocumentOut
from api.deps import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/users", response_model=List[dict])
async def admin_list_users(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(
            User.id, User.username, User.role, User.created_at,
            func.count(func.distinct(Document.id)).label("doc_count"),
            func.count(func.distinct(Conversation.id)).label("conv_count"),
        )
        .outerjoin(Document, Document.user_id == User.id)
        .outerjoin(Conversation, Conversation.user_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": str(r.id), "username": r.username, "role": r.role,
            "doc_count": r.doc_count, "conv_count": r.conv_count,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

@router.get("/documents", response_model=List[dict])
async def admin_list_documents(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Document, User.username)
        .join(User, Document.user_id == User.id)
        .order_by(Document.created_at.desc())
        .limit(200)
    )
    return [
        {
            "id": str(doc.id), "filename": doc.filename, "file_type": doc.file_type,
            "status": doc.status.value, "chunk_count": doc.chunk_count,
            "username": username, "created_at": doc.created_at.isoformat(),
        }
        for doc, username in result.all()
    ]

@router.get("/stats", response_model=dict)
async def admin_stats(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user_count = (await db.execute(select(func.count(User.id)))).scalar()
    doc_count = (await db.execute(select(func.count(Document.id)))).scalar()
    msg_count = (await db.execute(select(func.count(Message.id)))).scalar()
    new_users = (await db.execute(
        select(func.count(User.id)).where(
            User.created_at > func.now() - text("INTERVAL '7 days'")
        )
    )).scalar()
    return {
        "user_count": user_count,
        "doc_count": doc_count,
        "message_count": msg_count,
        "new_users_7d": new_users,
    }

@router.delete("/users/{user_id}", status_code=204)
async def admin_delete_user(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
```

- [ ] **Step 3: Register admin router in main.py**

In `api/main.py`:
```python
from api.admin import router as admin_router
app.include_router(admin_router)
```

- [ ] **Step 4: Create AdminView**

`frontend/src/views/AdminView.vue` — simplified table layout:
```vue
<template>
  <div class="admin-layout">
    <aside class="admin-sidebar">
      <h2>Admin</h2>
      <nav>
        <button :class="{ active: tab === 'users' }" @click="tab = 'users'">Users</button>
        <button :class="{ active: tab === 'docs' }" @click="tab = 'docs'">Documents</button>
        <button :class="{ active: tab === 'stats' }" @click="tab = 'stats'">Stats</button>
      </nav>
      <button class="back-btn" @click="$router.push('/chat')">← Back</button>
    </aside>
    <main class="admin-main">
      <!-- Users tab -->
      <div v-if="tab === 'users'">
        <h3>Users</h3>
        <table><thead><tr><th>Username</th><th>Role</th><th>Docs</th><th>Convs</th><th>Created</th><th>Action</th></tr></thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td>{{ u.username }}</td><td>{{ u.role }}</td><td>{{ u.doc_count }}</td><td>{{ u.conv_count }}</td>
              <td>{{ new Date(u.created_at).toLocaleDateString() }}</td>
              <td><button @click="deleteUser(u.id)" :disabled="deleting">Delete</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- Docs tab -->
      <div v-if="tab === 'docs'">...</div>
      <!-- Stats tab -->
      <div v-if="tab === 'stats'">...</div>
    </main>
  </div>
</template>
```

- [ ] **Step 5: Add admin route**

In `frontend/src/router/index.ts`:
```typescript
import AdminView from '../views/AdminView.vue'
// Add route:
{ path: '/admin', component: AdminView, meta: { requiresAuth: true, requiresAdmin: true } }
```

Add navigation guard for admin role.

- [ ] **Step 6: Add admin link in sidebar**

In `ChatView.vue` sidebar-footer, add admin link:
```vue
<router-link v-if="auth.user?.role === 'admin'" to="/admin" class="admin-link">管理</router-link>
```

- [ ] **Step 7: Write test**

In `tests/test_auth.py`:
```python
@pytest.mark.asyncio
async def test_admin_endpoint_rejects_non_admin(async_client, auth_headers):
    response = await async_client.get("/api/admin/stats", headers=auth_headers)
    assert response.status_code == 403
```

---

### Task 9: Document Categories

**Files:**
- Create: `api/categories.py`
- Modify: `api/main.py`
- Modify: `api/documents.py`
- Create: `frontend/src/components/CategorySelector.vue`
- Modify: `frontend/src/components/DocumentList.vue`
- Modify: `frontend/src/api/index.ts`
- Test: `tests/test_ingestion.py`

- [ ] **Step 1: Create categories router**

`api/categories.py`:
```python
import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import User, Category
from core.schemas import CategoryCreate, CategoryOut
from api.deps import get_current_user

router = APIRouter(prefix="/api/categories", tags=["categories"])

@router.get("", response_model=List[CategoryOut])
async def list_categories(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Category).where(Category.user_id == current_user.id).order_by(Category.name)
    )
    return result.scalars().all()

@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(
    req: CategoryCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cat = Category(id=uuid.uuid4(), user_id=current_user.id, name=req.name)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat

@router.put("/{cat_id}", response_model=CategoryOut)
async def update_category(
    cat_id: uuid.UUID, req: CategoryCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Category).where(Category.id == cat_id, Category.user_id == current_user.id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.name = req.name
    await db.commit()
    await db.refresh(cat)
    return cat

@router.delete("/{cat_id}", status_code=204)
async def delete_category(
    cat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Category).where(Category.id == cat_id, Category.user_id == current_user.id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    await db.delete(cat)
    await db.commit()
```

- [ ] **Step 2: Register categories router**

In `api/main.py`:
```python
from api.categories import router as categories_router
app.include_router(categories_router)
```

- [ ] **Step 3: Add category filter to document listing**

In `api/documents.py`, modify `list_documents` to accept optional `category` query param:
```python
@router.get("", response_model=List[DocumentOut])
async def list_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = None,  # NEW
):
    query = select(Document).where(Document.user_id == current_user.id)
    if category:
        query = query.where(Document.category_id == uuid.UUID(category))
    query = query.order_by(Document.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()
```

- [ ] **Step 4: Add PATCH endpoint to assign document category**

In `api/documents.py`:
```python
@router.patch("/{doc_id}/category", status_code=204)
async def set_document_category(
    doc_id: uuid.UUID,
    req: CategoryCreate,  # reuse with category_id field
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # req.name used as category_id
    doc.category_id = uuid.UUID(req.name) if req.name else None
    await db.commit()
```

- [ ] **Step 5: Create CategorySelector frontend**

`frontend/src/components/CategorySelector.vue` — dropdown filter + manage modal.

- [ ] **Step 6: Add frontend API methods**

In `frontend/src/api/index.ts`:
```typescript
async listCategories(): Promise<CategoryOut[]> { ... }
async createCategory(name: string): Promise<CategoryOut> { ... }
async deleteCategory(id: string): Promise<void> { ... }
```

- [ ] **Step 7: Write test**

```python
@pytest.mark.asyncio
async def test_category_crud(async_client, auth_headers):
    # Create category
    res = await async_client.post("/api/categories", json={"name": "Test"}, headers=auth_headers)
    assert res.status_code == 201
    cat_id = res.json()["id"]

    # List
    res = await async_client.get("/api/categories", headers=auth_headers)
    assert len(res.json()) == 1

    # Delete
    res = await async_client.delete(f"/api/categories/{cat_id}", headers=auth_headers)
    assert res.status_code == 204
```

---

### Task 10: Frontend Integration Polish

**Files:**
- Modify: `frontend/src/views/ChatView.vue`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Update MessageOut type**

In `frontend/src/api/index.ts`, extend `MessageOut`:
```typescript
export interface MessageOut {
  id: string
  role: string
  content: string
  sources: SourceItem[] | null
  created_at: string
  suggested_questions?: string[]  // NEW
}

export interface CategoryOut {
  id: string
  name: string
  created_at: string
}
```

- [ ] **Step 2: Add admin route guard**

In `frontend/src/router/index.ts`:
```typescript
// Admin guard
router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()
  if (to.meta.requiresAdmin && auth.user?.role !== 'admin') {
    next('/chat')
  } else {
    next()
  }
})
```

- [ ] **Step 3: Verify full flow end-to-end**

Run: `pytest tests/ -v`
Expected: All existing + new tests pass.
