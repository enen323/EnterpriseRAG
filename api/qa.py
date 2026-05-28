import json
import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import User, Conversation, Message, MessageFeedback, Document, DocumentStatus
from core.schemas import QARequest, QAResponse, SourceItem, FeedbackCreate
from api.deps import get_current_user
from rag.vector_store import search_documents
from rag.reranker import rerank_with_diversity
from rag.qa_chain import ask_question, extract_suggested_questions, generate_followup_questions
from rag.streaming import format_sse_event, generate_stream
from rag.memory import ConversationMemory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/qa", tags=["qa"])


@router.post("/ask", response_model=QAResponse)
async def ask(
    req: QARequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Resolve or create conversation
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

    # Check if user has ready documents
    doc_result = await db.execute(
        select(Document).where(Document.user_id == current_user.id, Document.status == DocumentStatus.READY)
    )
    docs = doc_result.scalars().all()
    if not docs:
        raise HTTPException(status_code=400, detail="No processed documents found. Upload documents first.")

    # Retrieve (user-scoped)
    raw_results = search_documents(req.question, filter={"user_id": str(current_user.id)})

    # Rerank
    reranked = rerank_with_diversity(req.question, raw_results)

    # Build source items from reranked results
    source_items = []
    for doc, score in reranked:
        source_items.append(SourceItem(
            filename=doc.metadata.get("source", "unknown"),
            chunk_text=doc.page_content[:200],
            score=score,
        ))

    # Build memory summary from previous conversation turns
    prev_result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    prev_messages = prev_result.scalars().all()

    memory = ConversationMemory()
    # Build summary from previous turns (excluding current user message)
    prev_pairs = []
    for i in range(0, len(prev_messages) - 1, 2):
        if i + 1 < len(prev_messages):
            prev_pairs.append((prev_messages[i].content, prev_messages[i + 1].content))

    # Rebuild summary from last 3 turns (token economy)
    for user_q, assistant_a in prev_pairs[-3:]:
        await memory.update_summary(user_q, assistant_a)

    memory_summary = memory.get_summary()

    # Ask LLM
    try:
        answer, parsed_sources, suggested = await ask_question(req.question, reranked, memory_summary)
    except Exception as e:
        logger.error(f"LLM call failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}")

    # Update memory with new turn
    await memory.update_summary(req.question, answer)

    # Save assistant message
    assistant_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        role="assistant",
        content=answer,
        sources=[s.model_dump() for s in source_items],
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    return QAResponse(
        answer=answer,
        sources=source_items,
        conversation_id=str(conv_id),
        message_id=str(assistant_msg.id),
        suggested_questions=suggested or None,
    )


@router.post("/ask/stream")
async def ask_stream(
    req: QARequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Stream a Q&A answer via Server-Sent Events.

    Pre-processing (conversation resolution, retrieval, reranking, memory) is
    identical to the non-streaming ``/ask`` endpoint.  After the LLM stream
    finishes, source parsing, follow-up generation, and DB persistence happen
    inside the generator before the final ``metadata`` event.
    """
    # Resolve or create conversation
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

    # Check if user has ready documents
    doc_result = await db.execute(
        select(Document).where(Document.user_id == current_user.id, Document.status == DocumentStatus.READY)
    )
    docs = doc_result.scalars().all()
    if not docs:
        raise HTTPException(status_code=400, detail="No processed documents found. Upload documents first.")

    # Retrieve (user-scoped)
    raw_results = search_documents(req.question, filter={"user_id": str(current_user.id)})

    # Rerank
    reranked = rerank_with_diversity(req.question, raw_results)

    # Build source items from reranked results
    source_items = []
    for doc, score in reranked:
        source_items.append(SourceItem(
            filename=doc.metadata.get("source", "unknown"),
            chunk_text=doc.page_content[:200],
            score=score,
        ))

    # Build memory summary from previous conversation turns
    prev_result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    prev_messages = prev_result.scalars().all()

    memory = ConversationMemory()
    prev_pairs = []
    for i in range(0, len(prev_messages) - 1, 2):
        if i + 1 < len(prev_messages):
            prev_pairs.append((prev_messages[i].content, prev_messages[i + 1].content))

    for user_q, assistant_a in prev_pairs[-3:]:
        await memory.update_summary(user_q, assistant_a)

    memory_summary = memory.get_summary()

    async def event_stream():
        """Inner async generator that drives the SSE stream."""
        full_answer = ""

        try:
            # Forward every event from the stream generator
            async for sse_str in generate_stream(req.question, reranked, memory_summary):
                # Parse the event to intercept ``done`` / ``error`` types
                if sse_str.startswith("data: "):
                    try:
                        payload = json.loads(sse_str[6:].strip())
                        event_type = payload.get("type")

                        if event_type == "token":
                            full_answer += payload["data"].get("token", "")
                            yield sse_str  # Forward to client

                        elif event_type == "done":
                            full_answer = payload["data"].get("answer", full_answer)
                            # Do NOT forward the raw ``done`` event -- we will
                            # emit a richer ``metadata`` event below.

                        elif event_type == "error":
                            yield sse_str  # Forward to client
                            return

                        else:
                            yield sse_str  # Unknown event type, pass through
                    except (json.JSONDecodeError, KeyError):
                        yield sse_str  # Unparseable, pass through
                else:
                    yield sse_str  # Non-data line, pass through

            if not full_answer:
                return

            # ---- post-stream processing ----

            # 1. Strip source markers from the raw answer
            from rag.qa_chain import _parse_sources

            clean_answer, source_filenames = _parse_sources(full_answer)

            # 2. Check for any inline Q: lines the LLM may have included
            clean_answer, _ = extract_suggested_questions(clean_answer)

            # 3. Generate follow-up questions via a lightweight LLM call
            suggested_questions = await generate_followup_questions(req.question, clean_answer)

            # 4. Update conversation memory with this turn
            await memory.update_summary(req.question, clean_answer)

            # 5. Persist assistant message
            assistant_msg_id = uuid.uuid4()
            assistant_msg = Message(
                id=assistant_msg_id,
                conversation_id=conv_id,
                role="assistant",
                content=clean_answer,
                sources=[s.model_dump() for s in source_items],
            )
            db.add(assistant_msg)
            await db.commit()

            # 6. Yield final metadata event
            yield format_sse_event("metadata", {
                "conversation_id": str(conv_id),
                "message_id": str(assistant_msg_id),
                "sources": [s.model_dump() for s in source_items],
                "suggested_questions": suggested_questions,
            })

        except Exception as e:
            logger.error(f"Stream endpoint error: {e}", exc_info=True)
            yield format_sse_event("error", {"message": f"Internal error: {str(e)}"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.patch("/feedback")
async def submit_feedback(
    req: FeedbackCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Submit or update feedback on an assistant message."""
    msg_result = await db.execute(
        select(Message)
        .join(Conversation)
        .where(Message.id == uuid.UUID(req.message_id), Conversation.user_id == current_user.id)
    )
    msg = msg_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

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
