"""
One-time data migration:  local SQLite  ->  cloud Postgres (Koyeb / Neon).

Run this ONCE from the backend/ folder, AFTER you have created the Postgres
database on Koyeb and copied its connection string.

    # Windows PowerShell, from the backend folder:
    $env:TARGET_DATABASE_URL = "postgres://USER:PASSWORD@HOST:5432/DBNAME"
    python migrate_to_postgres.py

It copies every table (users, cycles, alumni, relationships, documents, audit)
from yeshiva_alumni.db into the Postgres database in foreign-key-safe order,
preserving ids, then fixes the Postgres id sequences.

* Source is opened read-only; only the target is written.
* If the target already contains data it aborts (pass --force to override).
"""
import asyncio
import os
import sys
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from sqlalchemy import select, insert, text, func
from sqlalchemy.ext.asyncio import create_async_engine

# Importing the model modules registers every table on Base.metadata
from app.database import Base
from app.models import user, cycle, alumni, relationship, audit  # noqa: F401

SOURCE_URL = os.environ.get("SOURCE_DATABASE_URL", "sqlite+aiosqlite:///./yeshiva_alumni.db")


def _normalize_pg(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parts = urlsplit(url)
    kept = [(k, v) for k, v in parse_qsl(parts.query)
            if k.lower() not in ("sslmode", "channel_binding", "options")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))


async def main():
    target_raw = os.environ.get("TARGET_DATABASE_URL")
    if not target_raw:
        print("ERROR: set TARGET_DATABASE_URL to your Koyeb Postgres connection string first.")
        sys.exit(1)
    force = "--force" in sys.argv

    src = create_async_engine(SOURCE_URL)
    tgt = create_async_engine(_normalize_pg(target_raw), connect_args={"ssl": True})

    # 1) Create the schema on the target
    async with tgt.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tables = list(Base.metadata.sorted_tables)  # FK-dependency order

    # 2) Safety: refuse to run if the target already has data
    if not force:
        async with tgt.connect() as conn:
            for t in tables:
                n = (await conn.execute(select(func.count()).select_from(t))).scalar()
                if n:
                    print(f"Target already has {n} rows in '{t.name}'. "
                          f"Aborting to avoid duplicates (re-run with --force to override).")
                    sys.exit(1)

    # 3) Copy table by table
    print("Copying tables:")
    total = 0
    for t in tables:
        async with src.connect() as sconn:
            rows = (await sconn.execute(select(t))).mappings().all()
        if rows:
            async with tgt.begin() as tconn:
                await tconn.execute(insert(t), [dict(r) for r in rows])
        print(f"  {t.name:24s} {len(rows)}")
        total += len(rows)

    # 4) Reset Postgres id sequences so new inserts don't collide with copied ids
    async with tgt.begin() as conn:
        for t in tables:
            if "id" not in t.c:
                continue
            n = (await conn.execute(select(func.count()).select_from(t))).scalar()
            if not n:
                continue
            try:
                await conn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{t.name}', 'id'), "
                    f"(SELECT MAX(id) FROM {t.name}))"
                ))
            except Exception as e:
                print(f"  (sequence reset skipped for {t.name}: {e})")

    await src.dispose()
    await tgt.dispose()
    print(f"\nDone — copied {total} rows total. ✓")
    print("Verify in the app or via /docs that your alumni appear.")


if __name__ == "__main__":
    asyncio.run(main())
