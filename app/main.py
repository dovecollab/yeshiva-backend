from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from .config import settings
from .database import create_tables, AsyncSessionLocal
from .routers import auth, alumni, cycles, relationships, users

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="מערכת ניהול בוגרי ישיבה - API",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(auth.router, prefix="/api/v1")
app.include_router(alumni.router, prefix="/api/v1")
app.include_router(cycles.router, prefix="/api/v1")
app.include_router(relationships.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    if not settings.DEBUG and not settings.SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY לא הוגדר ב-.env — חובה להגדיר SECRET_KEY לפני הפעלה ב-production"
        )
    await create_tables()
    await _create_default_admin()


async def _create_default_admin():
    from sqlalchemy import select, func
    from .models.user import User
    from .utils.auth import get_password_hash
    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count()).select_from(User))).scalar()
        if count == 0:
            admin = User(
                username="admin",
                full_name="מנהל מערכת",
                role="admin",
                hashed_password=get_password_hash("admin123"),
                can_create=True, can_edit=True, can_delete=True,
                can_export=True, can_import=True, can_manage_users=True,
            )
            db.add(admin)
            await db.commit()
            print("✓ נוצר משתמש ברירת מחדל: admin / admin123")


@app.get("/")
def root():
    return {"message": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
