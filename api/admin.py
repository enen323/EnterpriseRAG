import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import User, Document, Message, Conversation
from api.deps import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
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
            "id": str(r.id), "username": r.username, "role": r.role.value if hasattr(r.role, 'value') else r.role,
            "doc_count": r.doc_count, "conv_count": r.conv_count,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/documents")
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
            "status": doc.status.value if hasattr(doc.status, 'value') else doc.status,
            "chunk_count": doc.chunk_count,
            "username": username, "created_at": doc.created_at.isoformat(),
        }
        for doc, username in result.all()
    ]


@router.get("/stats")
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
        "user_count": user_count or 0,
        "doc_count": doc_count or 0,
        "message_count": msg_count or 0,
        "new_users_7d": new_users or 0,
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
