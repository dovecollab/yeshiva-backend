from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict
from ..models.alumni import Alumni, AlumniDocument
from ..models.audit import AuditLog
from ..schemas.alumni import AlumniCreate, AlumniUpdate, AdvancedSearchRequest
from datetime import date, datetime


def _to_json_safe(d: dict) -> dict:
    result = {}
    for k, v in d.items():
        if isinstance(v, (date, datetime)):
            result[k] = v.isoformat()
        elif v is None:
            result[k] = None
        elif isinstance(v, (int, float, bool, str)):
            result[k] = v
        else:
            result[k] = str(v)
    return result


def _log_change(db: AsyncSession, record_id: int, action: str, changed_fields: dict, user_id: int, user_name: str):
    log = AuditLog(
        table_name="alumni",
        record_id=record_id,
        action=action,
        changed_fields=_to_json_safe(changed_fields),
        user_id=user_id,
        user_name=user_name,
    )
    db.add(log)


def _calculate_completeness(alumni: Alumni) -> float:
    weighted_fields = {
        "first_name": 10, "last_name": 10, "id_number": 15,
        "birth_date": 10, "phone": 15, "address": 10,
        "city": 10, "email": 10, "marital_status": 5, "photo_path": 5,
    }
    total_weight = sum(weighted_fields.values())
    earned = 0
    for field, weight in weighted_fields.items():
        val = getattr(alumni, field, None)
        if val is not None and str(val).strip() not in ("", "None", "none"):
            earned += weight
    return round((earned / total_weight) * 100, 1)


async def get_alumni(db: AsyncSession, alumni_id: int) -> Optional[Alumni]:
    return (await db.execute(
        select(Alumni)
        .options(
            selectinload(Alumni.cycle),
            selectinload(Alumni.documents),
            selectinload(Alumni.relationships_as_source),
            selectinload(Alumni.relationships_as_target),
        )
        .filter(Alumni.id == alumni_id)
    )).scalar_one_or_none()


async def get_alumni_list(
    db: AsyncSession, page: int = 1, page_size: int = 50,
    sort_by: str = "last_name", sort_desc: bool = False,
) -> Dict:
    total = (await db.execute(select(func.count(Alumni.id)))).scalar()

    col = getattr(Alumni, sort_by, Alumni.last_name)
    items = (await db.execute(
        select(Alumni)
        .options(selectinload(Alumni.cycle), selectinload(Alumni.documents))
        .order_by(col.desc() if sort_desc else col)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return {
        "items": items, "total": total, "page": page,
        "page_size": page_size, "total_pages": (total + page_size - 1) // page_size,
    }


async def advanced_search(db: AsyncSession, request: AdvancedSearchRequest) -> Dict:
    conditions = []

    if request.free_text:
        term = f"%{request.free_text}%"
        conditions.append(or_(
            Alumni.first_name.ilike(term),
            Alumni.last_name.ilike(term),
            Alumni.full_name.ilike(term),
            Alumni.phone.ilike(term),
            Alumni.phone2.ilike(term),
            Alumni.id_number.ilike(term),
            Alumni.email.ilike(term),
            Alumni.city.ilike(term),
            Alumni.address.ilike(term),
            Alumni.tags.ilike(term),
        ))
    for f in request.filters:
        col = getattr(Alumni, f.field, None)
        if col is None:
            continue
        if f.operator == "contains":
            conditions.append(col.ilike(f"%{f.value}%"))
        elif f.operator == "equals":
            conditions.append(col == f.value)
        elif f.operator == "starts_with":
            conditions.append(col.ilike(f"{f.value}%"))
        elif f.operator == "ends_with":
            conditions.append(col.ilike(f"%{f.value}"))

    if request.cycle_id:
        conditions.append(Alumni.cycle_id == request.cycle_id)
    if request.city:
        conditions.append(Alumni.city.ilike(f"%{request.city}%"))
    if request.marital_status:
        conditions.append(Alumni.marital_status == request.marital_status)
    if request.year_entry_from:
        conditions.append(Alumni.gregorian_year_entry >= request.year_entry_from)
    if request.year_entry_to:
        conditions.append(Alumni.gregorian_year_entry <= request.year_entry_to)
    if request.missing_fields:
        for field in request.missing_fields:
            col = getattr(Alumni, field, None)
            if col is not None:
                conditions.append(or_(col == None, col == ""))

    if request.tag:
        conditions.append(Alumni.tags.ilike(f"%{request.tag}%"))

    where_clause = and_(*conditions)

    total = (await db.execute(
        select(func.count(Alumni.id)).where(where_clause)
    )).scalar()

    sort_col = getattr(Alumni, request.sort_by, Alumni.last_name)
    items = (await db.execute(
        select(Alumni)
        .options(selectinload(Alumni.cycle), selectinload(Alumni.documents))
        .where(where_clause)
        .order_by(sort_col.desc() if request.sort_desc else sort_col)
        .offset((request.page - 1) * request.page_size)
        .limit(request.page_size)
    )).scalars().all()

    return {
        "items": items, "total": total, "page": request.page,
        "page_size": request.page_size,
        "total_pages": (total + request.page_size - 1) // request.page_size,
    }


async def create_alumni(db: AsyncSession, data: AlumniCreate, user_id: int, user_name: str) -> Alumni:
    alumni_data = data.dict()
    if not alumni_data.get("full_name"):
        alumni_data["full_name"] = f"{alumni_data['first_name']} {alumni_data['last_name']}".strip()

    alumni = Alumni(**alumni_data)
    db.add(alumni)
    await db.flush()
    alumni.completeness_score = _calculate_completeness(alumni)
    _log_change(db, alumni.id, "CREATE", alumni_data, user_id, user_name)
    await db.commit()
    return await get_alumni(db, alumni.id)


async def update_alumni(
    db: AsyncSession, alumni_id: int, data: AlumniUpdate, user_id: int, user_name: str
) -> Optional[Alumni]:
    alumni = (await db.execute(
        select(Alumni).filter(Alumni.id == alumni_id)
    )).scalar_one_or_none()
    if not alumni:
        return None

    update_data = data.dict(exclude_unset=True)
    changed_fields = {}
    for field, new_val in update_data.items():
        old_val = getattr(alumni, field, None)
        if old_val != new_val:
            changed_fields[field] = {"old": str(old_val), "new": str(new_val)}
            setattr(alumni, field, new_val)

    if "first_name" in update_data or "last_name" in update_data:
        alumni.full_name = f"{alumni.first_name} {alumni.last_name}".strip()

    alumni.completeness_score = _calculate_completeness(alumni)
    if changed_fields:
        _log_change(db, alumni_id, "UPDATE", changed_fields, user_id, user_name)
    await db.commit()
    return await get_alumni(db, alumni_id)


async def delete_alumni(db: AsyncSession, alumni_id: int, user_id: int, user_name: str) -> bool:
    alumni = (await db.execute(
        select(Alumni).filter(Alumni.id == alumni_id)
    )).scalar_one_or_none()
    if not alumni:
        return False
    _log_change(db, alumni_id, "DELETE", {"name": alumni.full_name}, user_id, user_name)
    await db.delete(alumni)
    await db.commit()
    return True


def alumni_to_dicts(alumni_list) -> List[Dict]:
    result = []
    for a in alumni_list:
        result.append({
            "id": a.id,
            "first_name": a.first_name or "",
            "last_name": a.last_name or "",
            "full_name": a.full_name or "",
            "id_number": a.id_number or "",
            "birth_date": a.birth_date.isoformat() if a.birth_date else "",
            "phone": a.phone or "",
            "phone2": a.phone2 or "",
            "address": a.address or "",
            "city": a.city or "",
            "email": a.email or "",
            "marital_status": a.marital_status or "",
            "hebrew_year_entry": a.hebrew_year_entry or "",
            "hebrew_year_exit": a.hebrew_year_exit or "",
            "gregorian_year_entry": a.gregorian_year_entry or "",
            "gregorian_year_exit": a.gregorian_year_exit or "",
            "notes": a.notes or "",
            "completeness_score": a.completeness_score or 0,
            "tags": a.tags or "",
            "created_at": a.created_at.isoformat() if a.created_at else "",
            "cycle_name": (a.cycle.name if a.cycle else ""),
        })
    return result


async def get_missing_data_report(db: AsyncSession) -> Dict:
    fields = ["phone", "address", "email", "id_number", "city", "photo_path"]
    report = {}
    for field in fields:
        col = getattr(Alumni, field)
        count = (await db.execute(
            select(func.count()).select_from(Alumni).where(or_(col == None, col == ""))
        )).scalar()
        report[field] = count
    report["total"] = (await db.execute(select(func.count(Alumni.id)))).scalar()
    return report


async def get_statistics(db: AsyncSession) -> Dict:
    total = (await db.execute(select(func.count(Alumni.id)))).scalar()

    by_city = (await db.execute(
        select(Alumni.city, func.count(Alumni.id))
        .filter(Alumni.city != None, Alumni.city != "")
        .group_by(Alumni.city)
        .order_by(func.count(Alumni.id).desc())
        .limit(20)
    )).all()

    by_marital = (await db.execute(
        select(Alumni.marital_status, func.count(Alumni.id))
        .filter(Alumni.marital_status != None)
        .group_by(Alumni.marital_status)
    )).all()

    by_year = (await db.execute(
        select(Alumni.gregorian_year_entry, func.count(Alumni.id))
        .filter(Alumni.gregorian_year_entry != None)
        .group_by(Alumni.gregorian_year_entry)
        .order_by(Alumni.gregorian_year_entry)
    )).all()

    avg_completeness = (await db.execute(
        select(func.avg(Alumni.completeness_score))
    )).scalar() or 0

    return {
        "total": total,
        "by_city": [{"city": r[0], "count": r[1]} for r in by_city],
        "by_marital_status": [{"status": r[0], "count": r[1]} for r in by_marital],
        "by_year": [{"year": r[0], "count": r[1]} for r in by_year],
        "avg_completeness": round(float(avg_completeness), 1),
    }
