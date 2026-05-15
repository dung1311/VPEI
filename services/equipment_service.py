from __future__ import annotations

from typing import Any, Optional, Type

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from models.emission_source import (
    CalculationMethodEnum,
    Scope1EmissionRecord,
    Scope1Equipment,
    Scope3EmissionRecord,
    Scope3Equipment,
    ScopeCategory,
)
from schemas.emission_source import (
    EquipmentCreate,
    EquipmentRecordCreate,
    EquipmentUpdate,
    ScopeCategoryCreate,
    ScopeCategoryUpdate,
)

GWP_CH4 = 28.0
GWP_N2O = 265.0

DEFAULT_SCOPE3_CATEGORIES = (
    ("A", "Phát thải từ vận chuyển và phân phối ngược dòng cho hàng hóa"),
    ("B", "Phát thải từ vận chuyển và phân phối upstream/downstream cho hàng hóa"),
    ("C", "Phát thải từ việc đi lại của nhân viên"),
    ("D", "Phát thải từ việc vận chuyển khách hàng và khách"),
    ("E", "Phát thải do đi công tác"),
    ("F", "Phát thải từ hàng hóa đã mua"),
    ("G", "Phát thải từ mua các dịch vụ"),
)


def _scope_models(scope: int) -> tuple[Type[Scope1Equipment], Type[Scope1EmissionRecord]]:
    if int(scope) == 1:
        return Scope1Equipment, Scope1EmissionRecord
    if int(scope) == 3:
        return Scope3Equipment, Scope3EmissionRecord
    raise HTTPException(status_code=400, detail="Scope không hợp lệ")


def _resolve_category(db: Session, scope: int, category_id: int) -> ScopeCategory:
    category = db.query(ScopeCategory).filter(
        ScopeCategory.id == category_id,
        ScopeCategory.scope == int(scope),
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="Không tìm thấy phạm vi")
    return category


def _format_code(scope: int, category_code: str, sequence_no: int) -> str:
    return f"{int(scope)}.{category_code.upper()}.{sequence_no}"


def _record_input(payload: EquipmentRecordCreate) -> dict[str, Any]:
    data = payload.model_dump()
    data.pop("equipment_id", None)
    data.pop("record_time", None)
    return jsonable_encoder({key: value for key, value in data.items() if value is not None})


def _calculate_co2e(method: CalculationMethodEnum, data: dict[str, Any]) -> float:
    if method == CalculationMethodEnum.METHOD_1:
        ef_co2 = float(data.get("ef_co2") or 0.0)
        ef_ch4 = float(data.get("ef_ch4") or 0.0)
        ef_n2o = float(data.get("ef_n2o") or 0.0)
        do_liters = float(data.get("do_liters") or 0.0)
        return round(do_liters * (ef_co2 + ef_ch4 * GWP_CH4 + ef_n2o * GWP_N2O), 6)
    if method in (CalculationMethodEnum.METHOD_2, CalculationMethodEnum.METHOD_3):
        mass = float(data.get("mass") or 0.0)
        ef = float(data.get("ef") or 0.0)
        return round(mass * ef, 6)
    if method == CalculationMethodEnum.METHOD_4:
        liters = float(data.get("liters") or 0.0)
        ef = float(data.get("ef") or 0.0)
        return round(liters * ef, 6)
    raise HTTPException(status_code=400, detail="Cách tính không hợp lệ")


def list_categories(db: Session, scope: int) -> list[ScopeCategory]:
    return db.query(ScopeCategory).filter(ScopeCategory.scope == int(scope)).order_by(
        ScopeCategory.sort_order.asc(),
        ScopeCategory.code.asc(),
    ).all()


def ensure_default_scope3_categories(db: Session) -> None:
    existing_codes = {
        row[0]
        for row in db.query(ScopeCategory.code).filter(ScopeCategory.scope == 3).all()
    }
    changed = False
    for idx, (code, name) in enumerate(DEFAULT_SCOPE3_CATEGORIES, start=1):
        if code in existing_codes:
            continue
        db.add(
            ScopeCategory(
                scope=3,
                code=code,
                name=name,
                sort_order=idx,
                is_active=1,
            )
        )
        changed = True
    if changed:
        db.commit()


def create_category(db: Session, payload: ScopeCategoryCreate) -> ScopeCategory:
    existing = db.query(ScopeCategory).filter(
        ScopeCategory.scope == int(payload.scope),
        ScopeCategory.code == payload.code,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mã phạm vi đã tồn tại")

    category = ScopeCategory(
        scope=int(payload.scope),
        code=payload.code,
        name=payload.name,
        description=payload.description,
        sort_order=payload.sort_order,
        is_active=1 if payload.is_active else 0,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category_id: int, payload: ScopeCategoryUpdate) -> ScopeCategory:
    category = db.query(ScopeCategory).filter(ScopeCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Không tìm thấy phạm vi")

    old_code = category.code
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "is_active" and value is not None:
            setattr(category, key, 1 if value else 0)
        elif value is not None:
            setattr(category, key, value)

    db.commit()
    db.refresh(category)

    if category.code != old_code:
        _sync_equipment_codes(db, category)

    return category


def delete_category(db: Session, category_id: int) -> dict[str, str]:
    category = db.query(ScopeCategory).filter(ScopeCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Không tìm thấy phạm vi để xóa")
    db.delete(category)
    db.commit()
    return {"message": "Đã xóa phạm vi"}


def _next_sequence(db: Session, equipment_model: Type[Scope1Equipment], category_id: int) -> int:
    current_max = db.query(func.max(equipment_model.sequence_no)).filter(
        equipment_model.category_id == category_id,
    ).scalar()
    return int(current_max or 0) + 1


def _sync_equipment_codes(db: Session, category: ScopeCategory) -> None:
    equipment_model, _ = _scope_models(category.scope)
    equipments = db.query(equipment_model).filter(equipment_model.category_id == category.id).all()
    for equipment in equipments:
        equipment.code = _format_code(category.scope, category.code, equipment.sequence_no)
    db.commit()


def create_equipment(db: Session, scope: int, payload: EquipmentCreate) -> Any:
    equipment_model, _ = _scope_models(scope)
    category = _resolve_category(db, scope, payload.category_id)

    normalized_name = payload.name.strip().casefold()
    existing = next(
        (
            equipment
            for equipment in db.query(equipment_model).all()
            if (equipment.name or "").strip().casefold() == normalized_name
        ),
        None,
    )
    if existing:
        existing.quantity = float(existing.quantity or 0.0) + float(payload.quantity or 0.0)
        if payload.unit:
            existing.unit = payload.unit
        if payload.description:
            existing.description = payload.description
        db.commit()
        db.refresh(existing)
        setattr(existing, "_was_quantity_incremented", True)
        return existing

    sequence_no = _next_sequence(db, equipment_model, category.id)
    code = _format_code(scope, category.code, sequence_no)

    equipment = equipment_model(
        category_id=category.id,
        sequence_no=sequence_no,
        code=code,
        name=payload.name,
        quantity=payload.quantity,
        unit=payload.unit,
        calculation_method=payload.calculation_method,
        emission_factor_json=payload.emission_factor_json,
        description=payload.description,
    )
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    return equipment


def update_equipment(db: Session, scope: int, equipment_id: int, payload: EquipmentUpdate) -> Any:
    equipment_model, _ = _scope_models(scope)
    equipment = db.query(equipment_model).filter(equipment_model.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")

    old_category_id = equipment.category_id
    update_data = payload.model_dump(exclude_unset=True)

    if "category_id" in update_data and update_data["category_id"] is not None:
        new_category = _resolve_category(db, scope, int(update_data["category_id"]))
        equipment.category_id = new_category.id
        if new_category.id != old_category_id:
            equipment.sequence_no = _next_sequence(db, equipment_model, new_category.id)
            equipment.code = _format_code(scope, new_category.code, equipment.sequence_no)
        update_data.pop("category_id")

    for key, value in update_data.items():
        setattr(equipment, key, value)

    if equipment.category_id != old_category_id:
        category = _resolve_category(db, scope, equipment.category_id)
        equipment.code = _format_code(scope, category.code, equipment.sequence_no)

    db.commit()
    db.refresh(equipment)
    return equipment


def delete_equipment(db: Session, scope: int, equipment_id: int) -> dict[str, str]:
    equipment_model, _ = _scope_models(scope)
    equipment = db.query(equipment_model).filter(equipment_model.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị để xóa")
    db.delete(equipment)
    db.commit()
    return {"message": "Đã xóa thiết bị"}


def list_equipments(db: Session, scope: int) -> list[Any]:
    equipment_model, _ = _scope_models(scope)
    return db.query(equipment_model).join(ScopeCategory, equipment_model.category_id == ScopeCategory.id).order_by(
        ScopeCategory.code.asc(),
        equipment_model.sequence_no.asc(),
    ).all()


def get_equipment(db: Session, scope: int, equipment_id: int) -> Any:
    equipment_model, _ = _scope_models(scope)
    equipment = db.query(equipment_model).filter(equipment_model.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")
    return equipment


def create_record(db: Session, scope: int, payload: EquipmentRecordCreate) -> Any:
    equipment_model, record_model = _scope_models(scope)
    equipment = db.query(equipment_model).filter(equipment_model.id == payload.equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")

    input_json = _record_input(payload)
    co2e = _calculate_co2e(equipment.calculation_method, input_json)
    record = record_model(
        equipment_id=equipment.id,
        record_time=payload.record_time,
        input_json=input_json,
        co2e=co2e,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def delete_record(db: Session, scope: int, record_id: int) -> dict[str, str]:
    _, record_model = _scope_models(scope)
    record = db.query(record_model).filter(record_model.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi thiết bị để xóa")
    db.delete(record)
    db.commit()
    return {"message": "Đã xóa bản ghi thiết bị"}


def list_records(db: Session, scope: int, year: Optional[int] = None, month: Optional[int] = None, quarter: Optional[int] = None) -> list[Any]:
    _, record_model = _scope_models(scope)
    query = db.query(record_model)
    if year is not None:
        query = query.filter(extract("year", record_model.record_time) == int(year))
    if month is not None:
        query = query.filter(extract("month", record_model.record_time) == int(month))
    elif quarter is not None:
        q = int(quarter)
        query = query.filter(extract("month", record_model.record_time).between((q - 1) * 3 + 1, q * 3))
    return query.order_by(record_model.record_time.desc()).all()


def get_equipment_detail(db: Session, scope: int, equipment_id: int) -> dict[str, Any]:
    equipment = get_equipment(db, scope, equipment_id)
    category = db.query(ScopeCategory).filter(ScopeCategory.id == equipment.category_id).first()
    _, record_model = _scope_models(scope)
    records = db.query(record_model).filter(record_model.equipment_id == equipment.id).order_by(record_model.record_time.desc()).all()
    return {"equipment": equipment, "category": category, "records": records}


def summary_by_scope(db: Session, scope: int, year: Optional[int] = None, month: Optional[int] = None, quarter: Optional[int] = None) -> dict[str, Any]:
    _, record_model = _scope_models(scope)
    query = db.query(func.sum(record_model.co2e))
    if year is not None:
        query = query.filter(extract("year", record_model.record_time) == int(year))
    if month is not None:
        query = query.filter(extract("month", record_model.record_time) == int(month))
    elif quarter is not None:
        q = int(quarter)
        query = query.filter(extract("month", record_model.record_time).between((q - 1) * 3 + 1, q * 3))
    total = float(query.scalar() or 0.0)

    records = list_records(db, scope, year=year, month=month, quarter=quarter)
    equipments = list_equipments(db, scope)
    equipment_map = {equipment.id: equipment for equipment in equipments}

    equipment_totals: dict[int, float] = {}
    category_totals: dict[int, float] = {}
    monthly_totals = [0.0] * 12

    for record in records:
        equipment = equipment_map.get(record.equipment_id)
        if not equipment:
            continue
        value = float(record.co2e or 0.0)
        equipment_totals[equipment.id] = equipment_totals.get(equipment.id, 0.0) + value
        category_totals[equipment.category_id] = category_totals.get(equipment.category_id, 0.0) + value
        if record.record_time:
            monthly_totals[record.record_time.month - 1] += value

    payload_categories = []
    for category in list_categories(db, scope):
        payload_categories.append({
            "id": category.id,
            "scope": category.scope,
            "code": category.code,
            "name": category.name,
            "description": category.description,
            "sort_order": category.sort_order,
            "is_active": bool(category.is_active),
            "total_co2e": float(category_totals.get(category.id, 0.0)),
        })

    payload_equipments = []
    for equipment in equipments:
        category = db.query(ScopeCategory).filter(ScopeCategory.id == equipment.category_id).first()
        payload_equipments.append({
            "id": equipment.id,
            "scope": scope,
            "code": equipment.code,
            "name": equipment.name,
            "quantity": equipment.quantity,
            "unit": equipment.unit,
            "calculation_method": equipment.calculation_method.value if equipment.calculation_method else None,
            "category_id": equipment.category_id,
            "category_code": category.code if category else "",
            "category_name": category.name if category else "",
            "total_co2e": float(equipment_totals.get(equipment.id, 0.0)),
        })

    top_equipment = None
    if equipment_totals:
        top_id = max(equipment_totals, key=equipment_totals.get)
        top_equipment = equipment_map.get(top_id)

    payload_records = []
    for record in records:
        equipment = equipment_map.get(record.equipment_id)
        payload_records.append({
            "id": record.id,
            "equipment_id": record.equipment_id,
            "equipment_code": equipment.code if equipment else "",
            "equipment_name": equipment.name if equipment else "",
            "record_time": record.record_time.strftime("%d/%m/%Y %H:%M") if record.record_time else "",
            "co2e": float(record.co2e or 0.0),
            "input_json": record.input_json or {},
        })

    return {
        "total_co2e": total,
        "equipment_totals": payload_equipments,
        "category_totals": payload_categories,
        "records": payload_records,
        "monthly_totals": monthly_totals,
        "top_equipment": {
            "id": top_equipment.id if top_equipment else None,
            "code": top_equipment.code if top_equipment else None,
            "name": top_equipment.name if top_equipment else None,
            "co2e": float(equipment_totals.get(top_equipment.id, 0.0)) if top_equipment else 0.0,
        } if top_equipment else None,
    }
