from datetime import datetime
from itertools import count
from io import BytesIO
import os
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from typing import Optional, List, Dict, Any
from openpyxl import Workbook, load_workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from models.electrical_item import ElectricalItem, ItemLocation

EF = 0.6235
_record_id_seq = count(1000)
MANAGER_RECORDS: List[Dict[str, Any]] = []
MANAGER_AUDIT: List[Dict[str, Any]] = []

def _now_vn() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")

def _add_audit(action_type: str, action: str, detail: str, user: str = "Admin"):
    MANAGER_AUDIT.insert(
        0,
        {
            "type": action_type,
            "action": action,
            "detail": detail,
            "user": user,
            "time": _now_vn(),
        },
    )

def _parse_entry_date(value: str) -> datetime:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError("entry_date must be yyyy-mm-dd or dd/mm/yyyy")


def _safe_pdf_text(value: Any) -> str:
    return str(value or "")


def _get_pdf_fonts() -> tuple[str, str]:
    regular_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]

    regular_path = next((p for p in regular_candidates if os.path.exists(p)), None)
    bold_path = next((p for p in bold_candidates if os.path.exists(p)), None)

    if regular_path and "DejaVuSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("DejaVuSans", regular_path))
    if bold_path and "DejaVuSans-Bold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold_path))

    if (
        "DejaVuSans" in pdfmetrics.getRegisteredFontNames()
        and "DejaVuSans-Bold" in pdfmetrics.getRegisteredFontNames()
    ):
        return ("DejaVuSans", "DejaVuSans-Bold")

    return ("Helvetica", "Helvetica-Bold")


def _normalize_location(value: str) -> ItemLocation:
    raw = (value or "").strip()
    for loc in ItemLocation:
        if raw == loc.value:
            return loc
    return ItemLocation.MAIN_PORT


def _parse_item_date(item: ElectricalItem) -> Optional[datetime]:
    try:
        return _parse_entry_date(item.period_value or "")
    except ValueError:
        return None


def _filter_items_by_period(
    items: List[ElectricalItem],
    mode: Optional[str] = None,
    bucket: Optional[str] = None,
    until_now: bool = False,
) -> List[ElectricalItem]:
    mode = (mode or "").strip().lower()
    bucket = (bucket or "").strip()
    now = datetime.now()

    def matches_mode(dt: datetime) -> bool:
        if not mode or not bucket:
            return True
        if mode == "day":
            return dt.strftime("%Y-%m-%d") == bucket
        if mode == "month":
            return dt.strftime("%Y-%m") == bucket
        if mode == "quarter":
            quarter = ((dt.month - 1) // 3) + 1
            return f"{dt.year}-Q{quarter}" == bucket
        if mode == "year":
            return str(dt.year) == bucket
        return True

    out: List[ElectricalItem] = []
    for item in items:
        dt = _parse_item_date(item)
        if dt is None:
            continue
        if until_now and dt > now:
            continue
        if not matches_mode(dt):
            continue
        out.append(item)
    return out

def get_scope2_categories(db: Session) -> List[Dict[str, Any]]:
    items_db = db.query(ElectricalItem).order_by(desc(ElectricalItem.id)).all()
    categories = []
    
    for item in items_db:
        entry_date_raw = (item.period_value or "").strip()
        try:
            dt = _parse_entry_date(entry_date_raw)
            entry_date = dt.strftime("%Y-%m-%d")
        except ValueError:
            entry_date = datetime.now().strftime("%Y-%m-%d")

        categories.append({
            "id": item.id,
            "name": item.name,
            "capacity": item.power,
            "area": item.location.value if item.location else "Cảng chính",
            "entry_date": entry_date,
            "kwh": int(item.power * 720 * 0.8),
            "note": item.description or ""
        })
    return categories

def get_manager_devices(db: Session) -> List[Dict[str, Any]]:
    items_db = db.query(ElectricalItem).order_by(desc(ElectricalItem.id)).all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "type": "Khác",
            "capacity": item.power,
            "area": item.location.value if item.location else "Cảng chính",
            "status": "active",
        }
        for item in items_db
    ]

def get_manager_records() -> List[Dict[str, Any]]:
    return MANAGER_RECORDS

def get_manager_audit() -> List[Dict[str, Any]]:
    return MANAGER_AUDIT

def get_ef() -> float:
    return EF

def create_electrical_item(item_data, db: Session) -> Dict[str, Any]:
    try:
        dt = _parse_entry_date(item_data.entry_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entry_date must be yyyy-mm-dd or dd/mm/yyyy",
        )

    try:
        location_enum = ItemLocation(item_data.location)
    except ValueError:
        location_enum = ItemLocation.MAIN_PORT

    db_item = ElectricalItem(
        name=item_data.name,
        power=item_data.power,
        location=location_enum,
        description=item_data.description,
        period_type="day",
        period_value=dt.strftime("%Y-%m-%d")
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    return {
        "id": db_item.id,
        "name": db_item.name,
        "capacity": db_item.power,
        "area": db_item.location.value if db_item.location else "Cảng chính",
        "entry_date": db_item.period_value,
        "kwh": int(db_item.power * 720 * 0.8),
        "note": db_item.description or ""
    }

def update_electrical_item(item_id: int, item_data, db: Session) -> Dict[str, Any]:
    db_item = db.query(ElectricalItem).filter(ElectricalItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    try:
        dt = _parse_entry_date(item_data.entry_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entry_date must be yyyy-mm-dd or dd/mm/yyyy",
        )

    try:
        location_enum = ItemLocation(item_data.location)
    except ValueError:
        location_enum = ItemLocation.MAIN_PORT

    db_item.name = item_data.name
    db_item.power = item_data.power
    db_item.location = location_enum
    db_item.description = item_data.description
    db_item.period_type = "day"
    db_item.period_value = dt.strftime("%Y-%m-%d")

    db.commit()
    db.refresh(db_item)

    return {
        "id": db_item.id,
        "name": db_item.name,
        "capacity": db_item.power,
        "area": db_item.location.value if db_item.location else "Cảng chính",
        "entry_date": db_item.period_value,
        "kwh": int(db_item.power * 720 * 0.8),
        "note": db_item.description or "",
    }

def delete_electrical_item(item_id: int, db: Session) -> Dict[str, Any]:
    db_item = db.query(ElectricalItem).filter(ElectricalItem.id == item_id).first()
    if not db_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    db.delete(db_item)
    db.commit()
    return {"ok": True, "deleted_id": item_id}


def import_scope2_items_from_excel(file_bytes: bytes, db: Session) -> Dict[str, Any]:
    try:
        wb = load_workbook(filename=BytesIO(file_bytes), data_only=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Excel file")

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {"ok": True, "imported": 0, "failed": 0, "errors": []}

    headers = [str(h).strip().lower() if h is not None else "" for h in rows[0]]
    idx_by_header = {h: i for i, h in enumerate(headers) if h}

    def find_index(*candidates: str) -> int:
        for c in candidates:
            if c in idx_by_header:
                return idx_by_header[c]
        return -1

    idx_name = find_index("name", "ten hang muc", "ten", "hạng mục", "tên hạng mục")
    idx_power = find_index("power", "cong suat", "công suất", "capacity")
    idx_location = find_index("location", "khu vuc", "khu vực", "area")
    idx_entry_date = find_index("entry_date", "ngay nhap", "ngày nhập", "date")
    idx_note = find_index("description", "note", "ghi chu", "ghi chú")

    if min(idx_name, idx_power, idx_location, idx_entry_date) < 0:
        raise HTTPException(
            status_code=400,
            detail="Excel must include columns: name, power, location, entry_date",
        )

    imported = 0
    failed = 0
    errors: List[str] = []

    for row_no, row in enumerate(rows[1:], start=2):
        try:
            name = str(row[idx_name] or "").strip()
            power = float(row[idx_power])
            location = _normalize_location(str(row[idx_location] or ""))
            entry_raw = str(row[idx_entry_date] or "").strip()
            note = str(row[idx_note] or "").strip() if idx_note >= 0 else ""

            if not name:
                raise ValueError("name is required")
            if power <= 0:
                raise ValueError("power must be > 0")

            try:
                dt = _parse_entry_date(entry_raw)
            except ValueError as ex:
                raise ValueError(str(ex))

            db_item = ElectricalItem(
                name=name,
                power=power,
                location=location,
                description=note,
                period_type="day",
                period_value=dt.strftime("%Y-%m-%d"),
            )
            db.add(db_item)
            imported += 1
        except Exception as ex:
            failed += 1
            errors.append(f"Row {row_no}: {ex}")

    db.commit()
    return {"ok": True, "imported": imported, "failed": failed, "errors": errors}


def export_scope2_items_excel(
    db: Session,
    mode: Optional[str] = None,
    bucket: Optional[str] = None,
    until_now: bool = False,
) -> bytes:
    items_db = db.query(ElectricalItem).order_by(desc(ElectricalItem.id)).all()
    items_db = _filter_items_by_period(items_db, mode=mode, bucket=bucket, until_now=until_now)

    wb = Workbook()
    ws = wb.active
    ws.title = "Scope2"
    ws.append(["STT", "Name", "Power(kW)", "Location", "Entry Date", "Description", "kWh (estimated)"])
    count = 0
    for item in items_db:
        count += 1
        ws.append([
            str(count),
            item.name,
            item.power,
            item.location.value if item.location else "Cảng chính",
            item.period_value or "",
            item.description or "",
            int(item.power * 720 * 0.8),
        ])

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def export_scope2_items_pdf(
    db: Session,
    mode: Optional[str] = None,
    bucket: Optional[str] = None,
    until_now: bool = False,
) -> bytes:
    items_db = db.query(ElectricalItem).order_by(desc(ElectricalItem.id)).all()
    items_db = _filter_items_by_period(items_db, mode=mode, bucket=bucket, until_now=until_now)
    normal_font, bold_font = _get_pdf_fonts()

    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    styles["Title"].fontName = bold_font
    styles["Normal"].fontName = normal_font

    elems = [
        Paragraph(_safe_pdf_text("Báo cáo Scope 2 - Danh mục điện năng"), styles["Title"]),
        Spacer(1, 10),
        # Paragraph(_safe_pdf_text(f"Generated at: {datetime.now().strftime('%d/%m/%Y %H:%M')}"), styles["Normal"]),
        Spacer(1, 12),
    ]

    data = [["STT", "Name", "Power(kW)", "Location", "Entry Date", "kWh"]]
    count = 0
    for item in items_db:
        count += 1
        data.append([
            str(count),
            _safe_pdf_text(item.name),
            f"{item.power:g}",
            _safe_pdf_text(item.location.value if item.location else "Cảng chính"),
            _safe_pdf_text(item.period_value or ""),
            str(int(item.power * 720 * 0.8)),
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d1f3c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTNAME", (0, 0), (-1, 0), bold_font),
        ("FONTNAME", (0, 1), (-1, -1), normal_font),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.Color(0.97, 0.98, 1)]),
    ]))

    elems.append(table)
    doc.build(elems)
    return out.getvalue()

def create_manager_record(payload) -> Dict[str, Any]:
    global _record_id_seq
    new_record = {
        "id": next(_record_id_seq),
        "device": payload.device,
        "kwh": payload.kwh,
        "from": payload.from_date or "",
        "to": payload.to_date or "",
        "period": payload.period,
        "note": payload.note or "",
    }
    MANAGER_RECORDS.append(new_record)
    _add_audit("add", "Thêm dữ liệu", f"{payload.device} – {int(payload.kwh):,} kWh – {payload.period}")
    return new_record

def delete_manager_record(record_id: int) -> Dict[str, Any]:
    idx = next((i for i, r in enumerate(MANAGER_RECORDS) if r["id"] == record_id), -1)
    if idx == -1:
        raise HTTPException(status_code=404, detail="Record not found")

    target = MANAGER_RECORDS[idx]
    del MANAGER_RECORDS[idx]
    _add_audit("del", "Xóa dữ liệu", f"{target['device']} – {int(target['kwh']):,} kWh – {target['period']}")
    return {"ok": True, "deleted_id": record_id}

def update_manager_record(record_id: int, payload) -> Dict[str, Any]:
    idx = next((i for i, r in enumerate(MANAGER_RECORDS) if r["id"] == record_id), -1)
    if idx == -1:
        raise HTTPException(status_code=404, detail="Record not found")

    MANAGER_RECORDS[idx] = {
        "id": record_id,
        "device": payload.device,
        "kwh": payload.kwh,
        "from": payload.from_date or "",
        "to": payload.to_date or "",
        "period": payload.period,
        "note": payload.note or "",
    }
    _add_audit("edit", "Ghi đè dữ liệu", f"{payload.device} – {int(payload.kwh):,} kWh – {payload.period}")
    return MANAGER_RECORDS[idx]

def mock_upload_excel() -> Dict[str, Any]:
    global _record_id_seq
    mock_rows = [
        {"device": "Cẩu điện", "kwh": 128000, "from": "01/06/2026", "to": "30/06/2026", "period": "Tháng 06/2026", "note": ""},
        {"device": "Kho lạnh", "kwh": 34000, "from": "01/06/2026", "to": "30/06/2026", "period": "Tháng 06/2026", "note": ""},
        {"device": "Văn phòng", "kwh": 8200, "from": "01/06/2026", "to": "30/06/2026", "period": "Tháng 06/2026", "note": ""},
    ]

    rows_with_id = []
    for row in mock_rows:
        row_with_id = {"id": next(_record_id_seq), **row}
        MANAGER_RECORDS.append(row_with_id)
        rows_with_id.append(row_with_id)

    _add_audit("upload", "Tải lên Excel", f"{len(mock_rows)} bản ghi – Thành công")
    return {
        "ok": True,
        "message": "Mock import success",
        "imported": len(mock_rows),
        "rows": rows_with_id,
        "warnings": ["Hàng 5: trùng kỳ báo cáo (mock warning)"]
    }
