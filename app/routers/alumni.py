from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import io
import os
import uuid
from ..database import get_db
from ..models.user import User
from ..models.alumni import Alumni
from ..schemas.alumni import (
    AlumniCreate, AlumniUpdate, AlumniResponse, AlumniDetailedResponse, AlumniListResponse, AdvancedSearchRequest
)
from ..services import alumni_service, import_export_service
from ..utils.auth import get_current_user, require_can_create, require_can_edit, require_can_delete
from ..config import settings

router = APIRouter(prefix="/alumni", tags=["alumni"])

_ALLOWED_PHOTO_EXTS = {".jpg", ".jpeg"}
_ALLOWED_PHOTO_MIME = {"image/jpeg", "image/jpg"}


@router.get("", response_model=AlumniListResponse)
async def list_alumni(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("last_name"),
    sort_desc: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await alumni_service.get_alumni_list(db, page, page_size, sort_by, sort_desc)


@router.post("/search", response_model=AlumniListResponse)
async def search_alumni(
    request: AdvancedSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await alumni_service.advanced_search(db, request)


@router.get("/statistics")
async def get_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await alumni_service.get_statistics(db)


@router.get("/missing-data")
async def get_missing_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await alumni_service.get_missing_data_report(db)


@router.get("/cities")
async def get_cities(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(Alumni.city)
        .filter(Alumni.city != None, Alumni.city != "")
        .group_by(Alumni.city)
        .order_by(Alumni.city)
    )).all()
    return [r[0] for r in rows]


@router.get("/tags")
async def get_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the sorted list of distinct tags across all alumni.

    Tags are stored as a comma-separated string per alumnus, so we split,
    strip and de-duplicate them here for use in autocomplete / pickers.
    """
    rows = (await db.execute(
        select(Alumni.tags).filter(Alumni.tags != None, Alumni.tags != "")
    )).all()
    tag_set = set()
    for (tags_str,) in rows:
        for t in (tags_str or "").split(","):
            t = t.strip()
            if t:
                tag_set.add(t)
    return sorted(tag_set)


@router.get("/sample-excel")
async def download_sample_excel(current_user: User = Depends(get_current_user)):
    import pandas as pd
    sample = [
        {
            "שם פרטי": "ישראל", "שם משפחה": "ישראלי", "תעודת זהות": "123456789",
            "תאריך לידה": "1990-05-15", "טלפון": "050-1234567", "טלפון נוסף": "",
            "כתובת": "רחוב הרצל 1", "עיר": "בני ברק", "מייל": "israel@example.com",
            "סטטוס אישי": "נשוי", "שנת כניסה עברית": 'תשע"ט', "שנת סיום עברית": 'תש"פ',
            "שנת כניסה": 2019, "שנת סיום": 2020, "הערות": ""
        },
        {
            "שם פרטי": "משה", "שם משפחה": "כהן", "תעודת זהות": "987654321",
            "תאריך לידה": "1988-03-20", "טלפון": "052-9876543", "טלפון נוסף": "03-1234567",
            "כתובת": "שד' ירושלים 45", "עיר": "ירושלים", "מייל": "",
            "סטטוס אישי": "נשוי", "שנת כניסה עברית": 'תש"פ', "שנת סיום עברית": 'תשפ"א',
            "שנת כניסה": 2020, "שנת סיום": 2021, "הערות": "בוגר מצטיין"
        },
    ]
    df = pd.DataFrame(sample)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="בוגרים")
        ws = writer.sheets["בוגרים"]
        ws.sheet_view.rightToLeft = True
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = max(
                len(str(col[0].value or "")), 12
            ) + 2
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="sample_alumni.xlsx"'},
    )


@router.get("/{alumni_id}", response_model=AlumniDetailedResponse)
async def get_alumni(
    alumni_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alumni = await alumni_service.get_alumni(db, alumni_id)
    if not alumni:
        raise HTTPException(status_code=404, detail="בוגר לא נמצא")
    return alumni


@router.post("", response_model=AlumniDetailedResponse, status_code=201)
async def create_alumni(
    data: AlumniCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_can_create),
):
    return await alumni_service.create_alumni(
        db, data, current_user.id, current_user.full_name or current_user.username
    )


@router.put("/{alumni_id}", response_model=AlumniDetailedResponse)
async def update_alumni(
    alumni_id: int,
    data: AlumniUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_can_edit),
):
    result = await alumni_service.update_alumni(
        db, alumni_id, data, current_user.id, current_user.full_name or current_user.username
    )
    if not result:
        raise HTTPException(status_code=404, detail="בוגר לא נמצא")
    return result


@router.delete("/{alumni_id}")
async def delete_alumni(
    alumni_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_can_delete),
):
    success = await alumni_service.delete_alumni(
        db, alumni_id, current_user.id, current_user.full_name or current_user.username
    )
    if not success:
        raise HTTPException(status_code=404, detail="בוגר לא נמצא")
    return {"message": "הבוגר נמחק בהצלחה"}


@router.post("/{alumni_id}/photo")
async def upload_photo(
    alumni_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_can_edit),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_PHOTO_EXTS:
        raise HTTPException(status_code=400, detail="סוג קובץ לא נתמך — יש להעלות תמונת JPG/JPEG בלבד")

    if file.content_type and file.content_type.lower() not in _ALLOWED_PHOTO_MIME:
        raise HTTPException(status_code=400, detail="סוג קובץ לא נתמך — יש להעלות תמונת JPG/JPEG בלבד")

    content = file.file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"הקובץ גדול מדי — גודל מקסימלי: {settings.MAX_FILE_SIZE_MB}MB",
        )

    alumni = (await db.execute(
        select(Alumni).filter(Alumni.id == alumni_id)
    )).scalar_one_or_none()
    if not alumni:
        raise HTTPException(status_code=404, detail="בוגר לא נמצא")

    upload_dir = os.path.join(settings.UPLOAD_DIR, "photos")
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{alumni_id}_{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    if alumni.photo_path and alumni.photo_path != file_path and os.path.exists(alumni.photo_path):
        try:
            os.remove(alumni.photo_path)
        except OSError:
            pass

    alumni.photo_path = file_path
    alumni.completeness_score = alumni_service._calculate_completeness(alumni)
    await db.commit()
    return {"photo_path": file_path}


@router.get("/{alumni_id}/audit")
async def get_audit_log(
    alumni_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from ..models.audit import AuditLog
    logs = (await db.execute(
        select(AuditLog)
        .filter(AuditLog.table_name == "alumni", AuditLog.record_id == alumni_id)
        .order_by(AuditLog.timestamp.desc())
    )).scalars().all()
    return logs


@router.post("/export/excel")
async def export_excel(
    request: AdvancedSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    params = request.model_dump()
    params.update({"page": 1, "page_size": 100000})
    result = await alumni_service.advanced_search(db, AdvancedSearchRequest(**params))
    rows = alumni_service.alumni_to_dicts(result["items"])
    content = import_export_service.export_to_excel(rows)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="alumni.xlsx"'},
    )


@router.post("/export/csv")
async def export_csv(
    request: AdvancedSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    params = request.model_dump()
    params.update({"page": 1, "page_size": 100000})
    result = await alumni_service.advanced_search(db, AdvancedSearchRequest(**params))
    rows = alumni_service.alumni_to_dicts(result["items"])
    content = import_export_service.export_to_csv(rows)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": 'attachment; filename="alumni.csv"'},
    )


@router.post("/import/excel")
async def import_excel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_can_create),
):
    content = file.file.read()
    return await import_export_service.import_from_excel(content, db, current_user.id)


@router.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_can_create),
):
    content = file.file.read()
    return await import_export_service.import_from_csv(content, db, current_user.id)
