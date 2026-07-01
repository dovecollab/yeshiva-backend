import io
import pandas as pd
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.alumni import Alumni


EXPORT_COLUMNS = [
    ("id", "מזהה"),
    ("first_name", "שם פרטי"),
    ("last_name", "שם משפחה"),
    ("full_name", "שם מלא"),
    ("id_number", "תעודת זהות"),
    ("birth_date", "תאריך לידה"),
    ("phone", "טלפון"),
    ("phone2", "טלפון נוסף"),
    ("address", "כתובת"),
    ("city", "עיר"),
    ("email", "מייל"),
    ("marital_status", "סטטוס אישי"),
    ("cycle_name", "מחזור"),
    ("hebrew_year_entry", "שנת כניסה עברית"),
    ("hebrew_year_exit", "שנת סיום עברית"),
    ("gregorian_year_entry", "שנת כניסה"),
    ("gregorian_year_exit", "שנת סיום"),
    ("notes", "הערות"),
    ("completeness_score", "אחוז שלמות"),
    ("created_at", "תאריך יצירה"),
]

IMPORT_COLUMNS = {
    "שם פרטי": "first_name",
    "שם משפחה": "last_name",
    "תעודת זהות": "id_number",
    "תאריך לידה": "birth_date",
    "טלפון": "phone",
    "טלפון נוסף": "phone2",
    "כתובת": "address",
    "עיר": "city",
    "מייל": "email",
    "סטטוס אישי": "marital_status",
    "שנת כניסה עברית": "hebrew_year_entry",
    "שנת סיום עברית": "hebrew_year_exit",
    "שנת כניסה": "gregorian_year_entry",
    "שנת סיום": "gregorian_year_exit",
    "הערות": "notes",
}


def export_to_excel(rows: List[Dict]) -> bytes:
    data = [{heb: r.get(eng, "") for eng, heb in EXPORT_COLUMNS} for r in rows]
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="בוגרים")
        worksheet = writer.sheets["בוגרים"]
        worksheet.sheet_view.rightToLeft = True
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            worksheet.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)
    return buf.getvalue()


def export_to_csv(rows: List[Dict]) -> bytes:
    data = [{heb: r.get(eng, "") for eng, heb in EXPORT_COLUMNS} for r in rows]
    df = pd.DataFrame(data)
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


async def import_from_excel(content: bytes, db: AsyncSession, user_id: int) -> Dict:
    df = pd.read_excel(io.BytesIO(content))
    return await _process_import_df(df, db, user_id)


async def import_from_csv(content: bytes, db: AsyncSession, user_id: int) -> Dict:
    df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    return await _process_import_df(df, db, user_id)


async def _process_import_df(df: pd.DataFrame, db: AsyncSession, user_id: int) -> Dict:
    created = 0
    updated = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            mapped = {}
            for col_name, val in row.items():
                eng_field = IMPORT_COLUMNS.get(str(col_name), col_name)
                if pd.isna(val):
                    mapped[eng_field] = None
                else:
                    mapped[eng_field] = str(val).strip() if val else None

            first_name = mapped.get("first_name", "")
            last_name = mapped.get("last_name", "")
            id_number = mapped.get("id_number") or mapped.get("תעודת זהות")

            if not first_name or not last_name:
                errors.append(f"שורה {idx+2}: חסר שם פרטי או שם משפחה")
                continue

            existing = None
            if id_number:
                existing = (await db.execute(
                    select(Alumni).filter(Alumni.id_number == id_number)
                )).scalar_one_or_none()

            if existing:
                for field in ["phone", "phone2", "address", "city", "email", "marital_status", "notes"]:
                    if mapped.get(field):
                        setattr(existing, field, mapped[field])
                updated += 1
            else:
                alumni = Alumni(
                    first_name=first_name,
                    last_name=last_name,
                    full_name=f"{first_name} {last_name}",
                    id_number=id_number,
                    phone=mapped.get("phone"),
                    phone2=mapped.get("phone2"),
                    address=mapped.get("address"),
                    city=mapped.get("city"),
                    email=mapped.get("email"),
                    marital_status=mapped.get("marital_status"),
                    notes=mapped.get("notes"),
                    created_by=user_id,
                )
                db.add(alumni)
                created += 1
        except Exception as e:
            errors.append(f"שורה {idx+2}: {str(e)}")

    await db.commit()
    return {"created": created, "updated": updated, "errors": errors}
