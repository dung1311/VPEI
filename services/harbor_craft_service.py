from __future__ import annotations
from typing import Any, Dict, List
from fastapi import HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session
from datetime import datetime

from models.harbor_craft import HarborCraft, HarborCraftTypeEnum, EngineTypeEnum
from schemas.harbor_craft import HarborCraftCreate, HarborCraftUpdate
from services import harbor_craft_activity_service

# Bảng tra cứu tự động Hệ số tải (LF)
HARBOR_CRAFT_LF_TABLE = {
    "atb": {"main": 0.50, "aux": 0.50},
    "assist_tug": {"main": 0.16, "aux": 0.34},
    "barge": {"main": 0.0, "aux": 0.31},
    "commercial_fishing": {"main": 0.27, "aux": 0.44},
    "crew_boat": {"main": 0.26, "aux": 0.40},
    "excursion": {"main": 0.27, "aux": 0.40},
    "ferry": {"main": 0.33, "aux": 0.39},
    "government": {"main": 0.33, "aux": 0.32},
    "ocean_tug": {"main": 0.50, "aux": 0.50},
    "tugboat": {"main": 0.16, "aux": 0.34},
    "work_boat": {"main": 0.33, "aux": 0.32},
    "other": {"main": 0.43, "aux": 0.43},
}

def _resolve_lf(craft_type: str, engine_type: str) -> float:
    """Tra cứu Load Factor từ bảng chuẩn"""
    craft = HARBOR_CRAFT_LF_TABLE.get(craft_type.lower(), HARBOR_CRAFT_LF_TABLE["other"])
    return craft.get(engine_type.lower(), 0.43)

def _resolve_cf_co2(use_rd99: bool, tier: str) -> float:
    """Tra cứu Control Factor (CF) cho CO2"""
    if not use_rd99:
        return 1.0
    if tier == "0-3":
        return 0.955
    return 1.0

def _compute_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Tự động nội suy toàn bộ biến phụ thuộc và tính E_total (Tập trung tính CO2)"""
    year_built = int(data.get("year_built", 2010))
    power = float(data.get("power", 0.0))
    activity_hours = float(data.get("activity_hours", 0.0))
    
    # Lấy giá trị chuỗi từ Enum
    c_type_obj = data.get("craft_type", HarborCraftTypeEnum.OTHER)
    craft_type_str = c_type_obj.value if hasattr(c_type_obj, 'value') else str(c_type_obj)
    
    e_type_obj = data.get("engine_type", EngineTypeEnum.MAIN)
    engine_type_str = e_type_obj.value if hasattr(e_type_obj, 'value') else str(e_type_obj)
    
    use_rd99 = bool(data.get("use_rd99", False))
    tier = str(data.get("engine_tier", "0-3"))
    
    record_time = data.get("record_time")
    period_year = record_time.year if record_time else datetime.now().year

    # 1. Nội suy tự động
    lf = _resolve_lf(craft_type_str, engine_type_str)
    zh = 762.0  # Cố định CO2
    dr = 0.0    # Cố định CO2
    fcf = 1.0   # Cố định CO2
    cf = _resolve_cf_co2(use_rd99, tier)

    # 2. Tính Cumulative Hours (Mỗi năm 4248h)
    age = max(0, period_year - year_built)
    annual_hours = 4248.0
    cumulative_hours = round(age * annual_hours, 2)

    # 3. Tính EF_final = ZH + (DR * Cumulative Hours)
    ef_final = zh + (dr * cumulative_hours)

    # 4. Tính e_total (Tấn CO2e)
    e_grams = power * activity_hours * lf * ef_final * fcf * cf
    e_total = round(e_grams / 1_000_000.0, 5)

    return {
        "lf": lf,
        "zh": zh,
        "dr": dr,
        "fcf": fcf,
        "cf": cf,
        "cumulative_hours": cumulative_hours,
        "ef_final": round(ef_final, 5),
        "e_total": e_total,
    }

def create_harbor_craft(
    craft_data: HarborCraftCreate,
    db: Session,
    actor: str = "system",
) -> Dict[str, Any]:
    input_data = craft_data.model_dump()
    computed = _compute_fields(input_data)
    
    new_craft = HarborCraft(
        device_name=craft_data.device_name,
        craft_type=craft_data.craft_type,
        engine_type=craft_data.engine_type,
        year_built=craft_data.year_built,
        power=craft_data.power,
        activity_hours=craft_data.activity_hours,
        use_rd99=craft_data.use_rd99,
        engine_tier=craft_data.engine_tier,
        lf=computed["lf"],
        zh=computed["zh"],
        dr=computed["dr"],
        fcf=computed["fcf"],
        cf=computed["cf"],
        cumulative_hours=computed["cumulative_hours"],
        ef_final=computed["ef_final"],
        e_total=computed["e_total"],
        record_time=craft_data.record_time,
    )
    db.add(new_craft)
    db.commit()
    db.refresh(new_craft)

    harbor_craft_activity_service.record_activity(
        db, actor, "Thêm dữ liệu Tàu cảng", 
        f"Tàu: {new_craft.device_name}, CO₂e: {new_craft.e_total:.2f} tấn"
    )

    return {"ok": True, "id": new_craft.id, "e_total": new_craft.e_total}

def get_all_harbor_crafts(db: Session) -> List[Dict[str, Any]]:
    crafts = db.query(HarborCraft).order_by(desc(HarborCraft.record_time)).all()
    return [
        {
            "id": c.id,
            "record_kind": "harbor_craft",
            "ui_type": "harbor_craft",
            "device_name": c.device_name,
            "craft_type": c.craft_type.value if hasattr(c.craft_type, 'value') else c.craft_type,
            "engine_type": c.engine_type.value if hasattr(c.engine_type, 'value') else c.engine_type,
            "year_built": c.year_built,
            "power": c.power,
            "activity_hours": c.activity_hours,
            "use_rd99": c.use_rd99,
            "engine_tier": c.engine_tier,
            "lf": c.lf,
            "zh": c.zh,
            "dr": c.dr,
            "cumulative_hours": c.cumulative_hours,
            "fcf": c.fcf,
            "cf": c.cf,
            "ef_final": c.ef_final,
            "e_total": c.e_total,
            "record_time": c.record_time.isoformat() if c.record_time else None,
        }
        for c in crafts
    ]

def update_harbor_craft(
    craft_id: int,
    craft_data: HarborCraftUpdate,
    db: Session,
    actor: str = "system",
) -> Dict[str, Any]:
    craft = db.query(HarborCraft).filter(HarborCraft.id == craft_id).first()
    if not craft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    update_data = craft_data.model_dump(exclude_unset=True)
    reason = update_data.pop("reason", None)
    if not reason or not str(reason).strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Update reason is required")

    for key, value in update_data.items():
        setattr(craft, key, value)

    computed = _compute_fields({
        "craft_type": craft.craft_type,
        "engine_type": craft.engine_type,
        "year_built": craft.year_built,
        "power": craft.power,
        "activity_hours": craft.activity_hours,
        "use_rd99": craft.use_rd99,
        "engine_tier": craft.engine_tier,
        "record_time": craft.record_time
    })
    
    for key, value in computed.items():
        setattr(craft, key, value)

    db.commit()
    db.refresh(craft)

    harbor_craft_activity_service.record_activity(
        db, actor, "Sửa dữ liệu Tàu cảng", 
        f"Tàu: {craft.device_name}, CO₂e: {craft.e_total:.2f} tấn, Lý do: {str(reason).strip()}"
    )

    return {"ok": True, "id": craft.id, "e_total": craft.e_total}

def delete_harbor_craft(
    craft_id: int,
    db: Session,
    actor: str = "system",
) -> Dict[str, Any]:
    craft = db.query(HarborCraft).filter(HarborCraft.id == craft_id).first()
    if not craft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    name = craft.device_name
    db.delete(craft)
    db.commit()

    harbor_craft_activity_service.record_activity(
        db, actor, "Xóa dữ liệu Tàu cảng", f"Tên tàu: {name}"
    )

    return {"ok": True, "deleted_id": craft_id}