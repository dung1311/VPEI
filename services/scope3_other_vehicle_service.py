from __future__ import annotations

import random
from typing import Any, Dict, List

from fastapi import HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.scope3_other_vehicle import Scope3OtherVehicle
from schemas.scope3_other_vehicle import Scope3OtherVehicleCreate
from services import container_activity_service


ALLOWED_TYPES = {"container-ship", "barge", "tugboat"}


def _random_ef(vehicle_type: str) -> float:
    ranges = {
        "container-ship": (2.85, 3.35),
        "barge": (2.70, 3.20),
        "tugboat": (2.80, 3.30),
    }
    low, high = ranges.get(vehicle_type, (2.7, 3.3))
    return round(random.uniform(low, high), 3)


def create_other_vehicle_record(
    payload: Scope3OtherVehicleCreate,
    db: Session,
    actor: str = "system",
) -> Dict[str, Any]:
    vehicle_type = (payload.vehicle_type or "").strip()
    if vehicle_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vehicle_type must be one of: container-ship, barge, tugboat",
        )

    if payload.trips < 0 or payload.consumption < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="trips and consumption must be >= 0",
        )

    ef = _random_ef(vehicle_type)
    e_total = round((payload.consumption * ef) / 1000.0, 5)

    rec = Scope3OtherVehicle(
        vehicle_type=vehicle_type,
        name=payload.name.strip(),
        period=payload.period.strip(),
        trips=payload.trips,
        consumption=payload.consumption,
        emission_factor=ef,
        e_total=e_total,
        note=(payload.note or "").strip() or None,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    container_activity_service.record_activity(
        db,
        actor,
        "Thêm dữ liệu phương tiện Scope 3",
        f"Loại: {rec.vehicle_type}, Tên: {rec.name}, CO₂e: {rec.e_total:.2f} tấn, EF(random): {rec.emission_factor:.3f}",
    )

    return {
        "ok": True,
        "id": rec.id,
        "vehicleType": rec.vehicle_type,
        "name": rec.name,
        "e_total": rec.e_total,
        "emission_factor": rec.emission_factor,
    }


def get_all_other_vehicle_records(db: Session) -> List[Dict[str, Any]]:
    rows = db.query(Scope3OtherVehicle).order_by(desc(Scope3OtherVehicle.created_at)).all()
    return [
        {
            "id": r.id,
            "record_kind": "other_vehicle",
            "vehicleType": r.vehicle_type,
            "name": r.name,
            "period": r.period,
            "trips": r.trips,
            "consumption": r.consumption,
            "emission_factor": r.emission_factor,
            "e_total": r.e_total,
            "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def delete_other_vehicle_record(record_id: int, db: Session, actor: str = "system") -> Dict[str, Any]:
    rec = db.query(Scope3OtherVehicle).filter(Scope3OtherVehicle.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    name = rec.name
    vtype = rec.vehicle_type
    db.delete(rec)
    db.commit()

    container_activity_service.record_activity(
        db,
        actor,
        "Xóa dữ liệu phương tiện Scope 3",
        f"Loại: {vtype}, Tên: {name}",
    )

    return {"ok": True, "deleted_id": record_id}
