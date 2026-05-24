import uuid
import logging
from typing import Annotated, List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import User, Conversation, Message
from core.schemas import ConversationOut, MessageOut
from api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=List[ConversationOut])
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{conv_id}", response_model=List[MessageOut])
async def get_conversation(
    conv_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Message)
        .join(Conversation)
        .where(Message.conversation_id == conv_id, Conversation.user_id == current_user.id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


@router.delete("/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == current_user.id)
    )
    conv = result.scalar_one_or_none()
    if conv:
        await db.delete(conv)
        await db.commit()
