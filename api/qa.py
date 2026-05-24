import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import User, Conversation, Message, Document, DocumentStatus
from core.schemas import QARequest, QAResponse, SourceItem
from api.deps import get_current_user
from rag.vector_store import search_documents
from rag.reranker import rerank
from rag.qa_chain import ask_question

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

    # Retrieve
    raw_results = search_documents(req.question)

    # Rerank
    reranked = rerank(req.question, raw_results)

    # Build source items from reranked results
    source_items = []
    for doc, score in reranked:
        source_items.append(SourceItem(
            filename=doc.metadata.get("source", "unknown"),
            chunk_text=doc.page_content[:200],
            score=score,
        ))

    # Memory summary (placeholder - will use real memory in Task 6)
    memory_summary = ""

    # Ask LLM
    try:
        answer, _ = await ask_question(req.question, reranked, memory_summary)
    except Exception as e:
        logger.error(f"LLM call failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}")

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

    return QAResponse(
        answer=answer,
        sources=source_items,
        conversation_id=str(conv_id),
    )
