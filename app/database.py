from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from .config import settings

# ── Normalize the DATABASE_URL to an async driver ────────────────────────────
_url = settings.DATABASE_URL

if _url.startswith("sqlite:///") and "+aiosqlite" not in _url:
    _url = _url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
elif _url.startswith("postgres://"):                       # Koyeb/Neon style
    _url = _url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _url.startswith("postgresql://") and "+asyncpg" not in _url:
    _url = _url.replace("postgresql://", "postgresql+asyncpg://", 1)

_is_sqlite = "sqlite" in _url
_is_postgres = "postgresql" in _url

_connect_args: dict = {}
_engine_kwargs: dict = {}

if _is_postgres:
    # asyncpg doesn't understand libpq query params (sslmode, channel_binding).
    # Strip them from the URL and enable TLS via connect_args instead — managed
    # Postgres providers like Koyeb and Neon require SSL.
    parts = urlsplit(_url)
    kept = [(k, v) for k, v in parse_qsl(parts.query)
            if k.lower() not in ("sslmode", "channel_binding", "options")]
    _url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))
    _connect_args = {"ssl": True}
    _engine_kwargs = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

engine = create_async_engine(_url, connect_args=_connect_args, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        yield db


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Dynamic schema upgrade: add 'tags' column if missing (works on SQLite + Postgres)
        from sqlalchemy import inspect, text
        try:
            def check_and_add_tags(sync_conn):
                inspector = inspect(sync_conn)
                columns = [c['name'] for c in inspector.get_columns('alumni')]
                if 'tags' not in columns:
                    sync_conn.execute(text("ALTER TABLE alumni ADD COLUMN tags VARCHAR(500) DEFAULT '';"))
                    print("✓ Database Migration: added tags column to alumni table")
            await conn.run_sync(check_and_add_tags)
        except Exception as e:
            print(f"⚠️ Database Migration Warning: {e}")
