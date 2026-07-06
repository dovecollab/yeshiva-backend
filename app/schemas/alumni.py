from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import date, datetime


class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: Optional[str]
    file_size: Optional[int]
    description: Optional[str]
    uploaded_at: datetime

    class Config:
        from_attributes = True


class AlumniBase(BaseModel):
    first_name: str
    last_name: str
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    birth_date: Optional[date] = None
    phone: Optional[str] = None
    phone2: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    email: Optional[str] = None
    marital_status: Optional[str] = None
    notes: Optional[str] = None
    cycle_id: Optional[int] = None
    hebrew_year_entry: Optional[str] = None
    hebrew_year_exit: Optional[str] = None
    gregorian_year_entry: Optional[int] = None
    gregorian_year_exit: Optional[int] = None
    tags: Optional[str] = ""

    @validator("full_name", always=True, pre=False)
    def set_full_name(cls, v, values):
        if not v:
            first = values.get("first_name", "")
            last = values.get("last_name", "")
            return f"{first} {last}".strip()
        return v


class AlumniCreate(AlumniBase):
    pass


class AlumniUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    birth_date: Optional[date] = None
    phone: Optional[str] = None
    phone2: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    email: Optional[str] = None
    marital_status: Optional[str] = None
    notes: Optional[str] = None
    cycle_id: Optional[int] = None
    hebrew_year_entry: Optional[str] = None
    hebrew_year_exit: Optional[str] = None
    gregorian_year_entry: Optional[int] = None
    gregorian_year_exit: Optional[int] = None
    tags: Optional[str] = ""


class AlumniResponse(AlumniBase):
    id: int
    photo_path: Optional[str] = None
    completeness_score: float = 0.0
    created_at: datetime
    updated_at: Optional[datetime] = None
    cycle_name: Optional[str] = None

    class Config:
        from_attributes = True

class AlumniDetailedResponse(AlumniResponse):
    documents: List[DocumentResponse] = []


class AlumniListResponse(BaseModel):
    items: List[AlumniResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SearchFilter(BaseModel):
    field: str
    operator: str  # contains, equals, starts_with, ends_with
    value: str


class AdvancedSearchRequest(BaseModel):
    filters: List[SearchFilter] = []
    free_text: Optional[str] = None
    cycle_id: Optional[int] = None
    city: Optional[str] = None
    marital_status: Optional[str] = None
    year_entry_from: Optional[int] = None
    year_entry_to: Optional[int] = None
    missing_fields: Optional[List[str]] = None
    tag: Optional[str] = None
    page: int = 1
    page_size: int = 50
    sort_by: str = "last_name"
    sort_desc: bool = False
