from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from ..database import get_db
from ..models.relationship import Relationship
from ..models.alumni import Alumni
from ..models.user import User
from ..schemas.relationship import RelationshipCreate, RelationshipResponse
from ..utils.auth import get_current_user, require_can_edit

router = APIRouter(prefix="/relationships", tags=["relationships"])


@router.get("/alumni/{alumni_id}", response_model=List[RelationshipResponse])
async def get_alumni_relationships(
    alumni_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rels = (await db.execute(
        select(Relationship).filter(
            (Relationship.alumni_id == alumni_id) | (Relationship.related_alumni_id == alumni_id)
        )
    )).scalars().all()

    result = []
    for r in rels:
        resp = RelationshipResponse.from_orm(r)
        if r.alumni_id == alumni_id:
            related = (await db.execute(
                select(Alumni).filter(Alumni.id == r.related_alumni_id)
            )).scalar_one_or_none()
        else:
            related = (await db.execute(
                select(Alumni).filter(Alumni.id == r.alumni_id)
            )).scalar_one_or_none()
        resp.related_name = related.full_name if related else None
        result.append(resp)
    return result


@router.post("", response_model=RelationshipResponse, status_code=201)
async def create_relationship(
    data: RelationshipCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_can_edit),
):
    if data.alumni_id == data.related_alumni_id:
        raise HTTPException(status_code=400, detail="לא ניתן לשייך בוגר לעצמו")

    existing = (await db.execute(
        select(Relationship).filter(
            Relationship.alumni_id == data.alumni_id,
            Relationship.related_alumni_id == data.related_alumni_id,
            Relationship.relationship_type == data.relationship_type,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="קשר זה כבר קיים")

    rel = Relationship(**data.dict(), created_by=current_user.id)
    db.add(rel)
    await db.commit()
    await db.refresh(rel)
    return rel


@router.delete("/{rel_id}")
async def delete_relationship(
    rel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_can_edit),
):
    rel = (await db.execute(
        select(Relationship).filter(Relationship.id == rel_id)
    )).scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="קשר לא נמצא")
    await db.delete(rel)
    await db.commit()
    return {"message": "הקשר נמחק"}
