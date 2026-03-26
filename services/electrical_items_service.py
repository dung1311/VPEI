from datetime import datetime
from itertools import count
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from typing import Optional, List, Dict, Any

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
