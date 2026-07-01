from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CycleBase(BaseModel):
    name: str
    hebrew_year: str
    gregorian_year_start: Optional[int] = None
    gregorian_year_end: Optional[int] = None
    description: Optional[str] = None


class CycleCreate(CycleBase):
    pass


class CycleUpdate(BaseModel):
    name: Optional[str] = None
    hebrew_year: Optional[str] = None
    gregorian_year_start: Optional[int] = None
    gregorian_year_end: Optional[int] = None
    description: Optional[str] = None


class CycleResponse(CycleBase):
    id: int
    alumni_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True
