from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RelationshipCreate(BaseModel):
    alumni_id: int
    related_alumni_id: int
    relationship_type: str
    notes: Optional[str] = None


class RelationshipResponse(BaseModel):
    id: int
    alumni_id: int
    related_alumni_id: int
    relationship_type: str
    notes: Optional[str] = None
    related_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
