from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from ..database import get_db
from ..models.cycle import Cycle
from ..models.user import User
from ..models.alumni import Alumni
from ..schemas.cycle import CycleCreate, CycleUpdate, CycleResponse
from ..utils.auth import get_current_user, require_admin

router = APIRouter(prefix="/cycles", tags=["cycles"])


def _to_response(cycle: Cycle, count: int) -> CycleResponse:
    """Build a CycleResponse from explicit column values + a pre-computed count.

    We deliberately do NOT use ``CycleResponse.from_orm(cycle)``: that makes
    Pydantic read the model's ``alumni_count`` property, which lazy-loads the
    ``alumni`` relationship. Under async SQLAlchemy a lazy load during
    serialization raises ``MissingGreenlet``. So the count is always queried
    inside the async session and passed in here, and only already-loaded
    columns are read off the cycle.
    """
    return CycleResponse(
        id=cycle.id,
        name=cycle.name,
        hebrew_year=cycle.hebrew_year,
        gregorian_year_start=cycle.gregorian_year_start,
        gregorian_year_end=cycle.gregorian_year_end,
        description=cycle.description,
        created_at=cycle.created_at,
        alumni_count=count or 0,
    )


async def _count_alumni(db: AsyncSession, cycle_id: int) -> int:
    return (await db.execute(
        select(func.count(Alumni.id)).filter(Alumni.cycle_id == cycle_id)
    )).scalar() or 0


@router.get("", response_model=List[CycleResponse])
async def list_cycles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cycles = (await db.execute(
        select(Cycle).order_by(Cycle.gregorian_year_start.desc())
    )).scalars().all()

    result = []
    for c in cycles:
        count = await _count_alumni(db, c.id)
        result.append(_to_response(c, count))
    return result


@router.post("", response_model=CycleResponse, status_code=201)
async def create_cycle(
    data: CycleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = (await db.execute(
        select(Cycle).filter(Cycle.name == data.name)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="מחזור עם שם זה כבר קיים")
    cycle = Cycle(**data.dict())
    db.add(cycle)
    await db.commit()
    await db.refresh(cycle)
    return _to_response(cycle, 0)


@router.put("/{cycle_id}", response_model=CycleResponse)
async def update_cycle(
    cycle_id: int,
    data: CycleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cycle = (await db.execute(
        select(Cycle).filter(Cycle.id == cycle_id)
    )).scalar_one_or_none()
    if not cycle:
        raise HTTPException(status_code=404, detail="מחזור לא נמצא")
    for field, val in data.dict(exclude_unset=True).items():
        setattr(cycle, field, val)
    await db.commit()
    await db.refresh(cycle)
    count = await _count_alumni(db, cycle.id)
    return _to_response(cycle, count)


@router.delete("/{cycle_id}")
async def delete_cycle(
    cycle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cycle = (await db.execute(
        select(Cycle).filter(Cycle.id == cycle_id)
    )).scalar_one_or_none()
    if not cycle:
        raise HTTPException(status_code=404, detail="מחזור לא נמצא")
    await db.delete(cycle)
    await db.commit()
    return {"message": "המחזור נמחק"}
