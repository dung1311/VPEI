from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.other_vehicle import OtherVehicle, OtherVehicleTypeEnum
from schemas.other_vehicle import OtherVehicleCreate, OtherVehicleUpdate
from services import container_activity_service

EMISSION_FACTOR_CAR = 0.082869
EMISSION_FACTOR_MOTORBIKE = 0.3362
DEFAULT_DISTANCE_KM = 1.0


def _normalize_vehicle_type(value: Any) -> OtherVehicleTypeEnum:
    if isinstance(value, OtherVehicleTypeEnum):
        return value
    try:
        return OtherVehicleTypeEnum(str(value))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vehicle_type must be car or motorbike",
        ) from exc


def _vehicle_type_label(vtype: OtherVehicleTypeEnum) -> str:
    return "O to thuong" if vtype == OtherVehicleTypeEnum.CAR else "Xe may"


def _compute_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    vtype = _normalize_vehicle_type(data.get("vehicle_type"))
    try:
        count = int(data.get("vehicle_count") or 0)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vehicle_count must be a number",
        ) from exc

    if count <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vehicle_count must be >= 1",
        )

    ef = EMISSION_FACTOR_CAR if vtype == OtherVehicleTypeEnum.CAR else EMISSION_FACTOR_MOTORBIKE
    distance = DEFAULT_DISTANCE_KM
    e_total = round(count * ef * distance, 6)

    return {
        "vehicle_type": vtype,
        "vehicle_count": count,
        "emission_factor": ef,
        "distance_km": distance,
        "e_total": e_total,
    }


def create_other_vehicle(
    payload: OtherVehicleCreate,
    db: Session,
    actor: str = "system",
) -> Dict[str, Any]:
    input_data = payload.model_dump()
    computed = _compute_fields(input_data)

    new_record = OtherVehicle(
        vehicle_type=computed["vehicle_type"],
        vehicle_count=computed["vehicle_count"],
        emission_factor=computed["emission_factor"],
        distance_km=computed["distance_km"],
        e_total=computed["e_total"],
        record_time=payload.record_time,
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    container_activity_service.record_activity(
        db,
        actor,
        "Them du lieu xe thuong",
        f"Loai: {_vehicle_type_label(new_record.vehicle_type)}, So luong: {new_record.vehicle_count}, CO2e: {new_record.e_total:.4f} tan",
    )

    return {
        "ok": True,
        "id": new_record.id,
        "e_total": new_record.e_total,
    }


def get_all_other_vehicles(db: Session) -> List[Dict[str, Any]]:
    records = db.query(OtherVehicle).order_by(desc(OtherVehicle.record_time)).all()
    return [
        {
            "id": r.id,
            "record_kind": "other_vehicle",
            "vehicle_type": r.vehicle_type.value if hasattr(r.vehicle_type, "value") else str(r.vehicle_type),
            "vehicle_count": r.vehicle_count,
            "emission_factor": r.emission_factor,
            "distance_km": r.distance_km,
            "e_total": r.e_total,
            "record_time": r.record_time.isoformat() if r.record_time else None,
        }
        for r in records
    ]


def get_other_vehicle_by_id(record_id: int, db: Session) -> Dict[str, Any]:
    record = db.query(OtherVehicle).filter(OtherVehicle.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    return {
        "id": record.id,
        "vehicle_type": record.vehicle_type.value if hasattr(record.vehicle_type, "value") else str(record.vehicle_type),
        "vehicle_count": record.vehicle_count,
        "emission_factor": record.emission_factor,
        "distance_km": record.distance_km,
        "e_total": record.e_total,
        "record_time": record.record_time.isoformat() if record.record_time else None,
    }


def update_other_vehicle(
    record_id: int,
    payload: OtherVehicleUpdate,
    db: Session,
    actor: str = "system",
) -> Dict[str, Any]:
    record = db.query(OtherVehicle).filter(OtherVehicle.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    update_data = payload.model_dump(exclude_unset=True)
    reason = update_data.pop("reason", None)
    if not reason or not str(reason).strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Update reason is required")

    for key, value in update_data.items():
        setattr(record, key, value)

    computed = _compute_fields(
        {
            "vehicle_type": record.vehicle_type,
            "vehicle_count": record.vehicle_count,
        }
    )
    record.vehicle_type = computed["vehicle_type"]
    record.vehicle_count = computed["vehicle_count"]
    record.emission_factor = computed["emission_factor"]
    record.distance_km = computed["distance_km"]
    record.e_total = computed["e_total"]

    db.commit()
    db.refresh(record)

    container_activity_service.record_activity(
        db,
        actor,
        "Sua du lieu xe thuong",
        f"Loai: {_vehicle_type_label(record.vehicle_type)}, So luong: {record.vehicle_count}, CO2e: {record.e_total:.4f} tan, Ly do: {str(reason).strip()}",
    )

    return {"ok": True, "id": record.id, "e_total": record.e_total}


def delete_other_vehicle(
    record_id: int,
    db: Session,
    actor: str = "system",
) -> Dict[str, Any]:
    record = db.query(OtherVehicle).filter(OtherVehicle.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    name = _vehicle_type_label(record.vehicle_type)
    db.delete(record)
    db.commit()

    container_activity_service.record_activity(
        db,
        actor,
        "Xoa du lieu xe thuong",
        f"Loai: {name}, So luong: {record.vehicle_count}",
    )

    return {"ok": True, "deleted_id": record_id}
