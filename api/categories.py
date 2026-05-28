import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import User, Category
from core.schemas import CategoryCreate, CategoryOut
from api.deps import get_current_user

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
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
    cat_id: uuid.UUID,
    req: CategoryCreate,
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
