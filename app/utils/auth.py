from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models.user import User
from ..config import settings

security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.effective_secret_key, algorithm=settings.ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="אישורים לא תקינים",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.effective_secret_key, algorithms=[settings.ALGORITHM])
        raw_sub = payload.get("sub")
        if raw_sub is None:
            raise credentials_exception
        # The JWT stores the id as a string. Postgres (unlike SQLite) will not
        # compare an integer column to a string param, so cast it to int here.
        try:
            user_id = int(raw_sub)
        except (TypeError, ValueError):
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = (await db.execute(
        select(User).filter(User.id == user_id, User.is_active == True)
    )).scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="נדרשות הרשאות מנהל")
    return current_user


async def require_can_edit(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role == "viewer" and not current_user.can_edit:
        raise HTTPException(status_code=403, detail="אין הרשאה לעריכה")
    return current_user


async def require_can_create(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role == "viewer" and not current_user.can_create:
        raise HTTPException(status_code=403, detail="אין הרשאה ליצירה")
    return current_user


async def require_can_delete(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin",) and not current_user.can_delete:
        raise HTTPException(status_code=403, detail="אין הרשאה למחיקה")
    return current_user
