from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from ..database import get_db
from ..models.user import User
from ..schemas.user import UserCreate, UserUpdate, UserResponse
from ..utils.auth import get_password_hash, require_admin, get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return (await db.execute(select(User))).scalars().all()


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if (await db.execute(
        select(User).filter(User.username == data.username)
    )).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="שם משתמש כבר קיים")

    user_data = data.dict(exclude={"password"})
    user = User(**user_data, hashed_password=get_password_hash(data.password))

    if data.role == "admin":
        user.can_create = user.can_edit = user.can_delete = user.can_export = user.can_import = user.can_manage_users = True
    elif data.role == "secretary":
        user.can_create = user.can_edit = user.can_export = user.can_import = True

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = (await db.execute(
        select(User).filter(User.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")

    update_data = data.dict(exclude_unset=True, exclude={"password"})
    for field, val in update_data.items():
        setattr(user, field, val)

    if data.password:
        user.hashed_password = get_password_hash(data.password)

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="לא ניתן למחוק את המשתמש הנוכחי")
    user = (await db.execute(
        select(User).filter(User.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")
    await db.delete(user)
    await db.commit()
    return {"message": "המשתמש נמחק"}
