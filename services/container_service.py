from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.container import Container, ContainerWeightType, JourneyType
from schemas.container import ContainerCreate, ContainerUpdate
from services import container_activity_service


def _resolve_container_weight_type(max_weight: float) -> ContainerWeightType:
    # Keep type_1 for standard <= 40 ton truck; type_2 for heavier settings.
    return ContainerWeightType.TYPE_1 if (max_weight or 40.0) <= 40 else ContainerWeightType.TYPE_2


def _interpolated_ef(weight_type: ContainerWeightType, payload_ratio: float, is_refrigerated: bool) -> float:
    x_data = [0.0, 50.0, 100.0]
    
    if not is_refrigerated:
        if weight_type == ContainerWeightType.TYPE_1:
            y_data = [0.61562, 0.76647, 0.91733]
        else:
            y_data = [0.6325, 0.83849, 1.04448]
    else:
        if weight_type == ContainerWeightType.TYPE_1:
            y_data = [0.72566, 0.90403, 1.08239]
        else:
            y_data = [0.748, 0.99249, 1.23699]

    payload_percent = max(0.0, min(100.0, payload_ratio * 100.0))
    if payload_percent <= x_data[1]:
        x0, x1 = x_data[0], x_data[1]
        y0, y1 = y_data[0], y_data[1]
    else:
        x0, x1 = x_data[1], x_data[2]
        y0, y1 = y_data[1], y_data[2]

    ratio = 0.0 if x1 == x0 else (payload_percent - x0) / (x1 - x0)
    ef = y0 + (y1 - y0) * ratio
    return round(ef, 5)


def _compute_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    max_weight = float(data.get("max_weight") or 40.0)
    if max_weight <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="max_weight must be > 0")

    start_time = data["start_time"]
    end_time = data["end_time"]
    if end_time <= start_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_time must be after start_time")

    duration = (end_time - start_time).total_seconds() / 3600.0
    journey_type = data["journey_type"]
    if isinstance(journey_type, str):
        journey_type = JourneyType(journey_type)

    velocity_1 = float(data["velocity_1"])
    velocity_2 = float(data["velocity_2"])
    velocity_3 = float(data["velocity_3"])
    if min(velocity_1, velocity_2, velocity_3) <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All leg velocities must be > 0")

    distance_1 = float(data["distance_1"])
    distance_2 = float(data["distance_2"])
    distance_3 = float(data["distance_3"])
    input_weight = float(data["input_weight"])
    output_weight = float(data["output_weight"])

    if min(distance_1, distance_2, distance_3, input_weight, output_weight) < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Distances and weights must be >= 0")

    if journey_type == JourneyType.BOTH:
        payload_1 = input_weight / max_weight
        payload_2 = 0.0
        payload_3 = output_weight / max_weight
    elif journey_type == JourneyType.EXPORT_ONLY:
        payload_1 = 0.0
        payload_2 = output_weight / max_weight
        payload_3 = 0.0
    else:
        payload_1 = input_weight / max_weight
        payload_2 = 0.0
        payload_3 = 0.0

    payload_1 = round(payload_1, 3)
    payload_2 = round(payload_2, 3)
    payload_3 = round(payload_3, 3)

    is_refrigerated = data.get("is_refrigerated", False)

    container_weight_type = _resolve_container_weight_type(max_weight)
    ef1 = _interpolated_ef(container_weight_type, payload_1, is_refrigerated)
    ef2 = _interpolated_ef(container_weight_type, payload_2, is_refrigerated)
    ef3 = _interpolated_ef(container_weight_type, payload_3, is_refrigerated)

    time1 = round(distance_1 / velocity_1, 5)
    time2 = round(distance_2 / velocity_2, 5)
    time3 = round(distance_3 / velocity_3, 5)

    e_1 = distance_1 * ef1
    e_2 = distance_2 * ef2
    e_3 = distance_3 * ef3
    waited_time = max(0.0, duration - (time1 + time2 + time3))
    active_waited_time = round(waited_time * 0.22, 5)
    e_total_kg = e_1 + e_2 + e_3 + active_waited_time * 6.688605
    e_total = round(e_total_kg / 1000.0, 5)
    return {
        "duration": round(duration, 5),
        "max_weight": max_weight,
        "journey_type": journey_type,
        "container_weight_type": container_weight_type,
        "velocity_1": velocity_1,
        "velocity_2": velocity_2,
        "velocity_3": velocity_3,
        "velocity": round((velocity_1 + velocity_2 + velocity_3) / 3.0, 5),
        "payload_1": payload_1,
        "payload_2": payload_2,
        "payload_3": payload_3,
        "ef1": ef1,
        "ef2": ef2,
        "ef3": ef3,
        "time1": time1,
        "time2": time2,
        "time3": time3,
        "waited_time": round(waited_time, 5),
        "active_waited_time": active_waited_time,
        "e_total": e_total,
    }


def create_container(
    container_data: ContainerCreate,
    db: Session,
    actor: str = "system",
) -> Dict[str, Any]:
    """Create new container record"""
    input_data = container_data.dict()
    computed = _compute_fields(input_data)
    new_container = Container(
        license_plate=container_data.license_plate,
        start_time=container_data.start_time,
        end_time=container_data.end_time,
        is_refrigerated=container_data.is_refrigerated,
        max_weight=computed["max_weight"],
        journey_type=computed["journey_type"],
        container_weight_type=computed["container_weight_type"],
        velocity=computed["velocity"],
        velocity_1=computed["velocity_1"],
        velocity_2=computed["velocity_2"],
        velocity_3=computed["velocity_3"],
        input_weight=container_data.input_weight,
        output_weight=container_data.output_weight,
        distance_1=container_data.distance_1,
        distance_2=container_data.distance_2,
        distance_3=container_data.distance_3,
        duration=computed["duration"],
        payload_1=computed["payload_1"],
        payload_2=computed["payload_2"],
        payload_3=computed["payload_3"],
        ef1=computed["ef1"],
        ef2=computed["ef2"],
        ef3=computed["ef3"],
        time1=computed["time1"],
        time2=computed["time2"],
        time3=computed["time3"],
        waited_time=computed["waited_time"],
        active_waited_time=computed["active_waited_time"],
        e_total=computed["e_total"],
    )
    db.add(new_container)
    db.commit()
    db.refresh(new_container)

    container_activity_service.record_activity(
        db,
        actor,
        "Thêm dữ liệu container",
        f"Biển xe: {new_container.license_plate}, CO₂e: {new_container.e_total:.2f} tấn",
    )

    return {
        "ok": True,
        "id": new_container.id,
        "license_plate": new_container.license_plate,
        "e_total": new_container.e_total,
    }


def get_all_containers(db: Session) -> List[Dict[str, Any]]:
    """Get all container records"""
    containers = db.query(Container).order_by(desc(Container.start_time)).all()
    return [
        {
            "id": c.id,
            "record_kind": "container",
            "vehicleType": "truck",
            "license_plate": c.license_plate,
            "start_time": c.start_time.isoformat(),
            "end_time": c.end_time.isoformat(),
            "duration": c.duration,
            "max_weight": c.max_weight,
            "is_refrigerated": bool(c.is_refrigerated),
            "journey_type": c.journey_type.value if c.journey_type else None,
            "velocity": c.velocity,
            "velocity_1": c.velocity_1,
            "velocity_2": c.velocity_2,
            "velocity_3": c.velocity_3,
            "distance_1": c.distance_1,
            "distance_2": c.distance_2,
            "distance_3": c.distance_3,
            "input_weight": c.input_weight,
            "output_weight": c.output_weight,
            "e_total": c.e_total,
        }
        for c in containers
    ]


def get_container_by_id(container_id: int, db: Session) -> Dict[str, Any]:
    """Get specific container record"""
    container = db.query(Container).filter(Container.id == container_id).first()
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container not found",
        )

    return {
        "id": container.id,
        "license_plate": container.license_plate,
        "start_time": container.start_time.isoformat(),
        "end_time": container.end_time.isoformat(),
        "duration": container.duration,
        "max_weight": container.max_weight,
        "journey_type": container.journey_type.value if container.journey_type else None,
        "container_weight_type": container.container_weight_type.value if container.container_weight_type else None,
        "velocity": container.velocity,
        "velocity_1": container.velocity_1,
        "velocity_2": container.velocity_2,
        "velocity_3": container.velocity_3,
        "input_weight": container.input_weight,
        "output_weight": container.output_weight,
        "payload_1": container.payload_1,
        "payload_2": container.payload_2,
        "payload_3": container.payload_3,
        "ef1": container.ef1,
        "ef2": container.ef2,
        "ef3": container.ef3,
        "distance_1": container.distance_1,
        "distance_2": container.distance_2,
        "distance_3": container.distance_3,
        "time1": container.time1,
        "time2": container.time2,
        "time3": container.time3,
        "waited_time": container.waited_time,
        "active_waited_time": container.active_waited_time,
        "e_total": container.e_total,
    }


def update_container(
    container_id: int,
    container_data: ContainerUpdate,
    db: Session,
    actor: str = "system",
) -> Dict[str, Any]:
    """Update container record"""
    container = db.query(Container).filter(Container.id == container_id).first()
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container not found",
        )

    update_data = container_data.dict(exclude_unset=True)
    reason = update_data.pop("reason", None)
    if not reason or not str(reason).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Update reason is required",
        )

    for key, value in update_data.items():
        setattr(container, key, value)

    computed = _compute_fields(
        {
            "start_time": container.start_time,
            "end_time": container.end_time,
            "max_weight": container.max_weight,
            "journey_type": container.journey_type,
            "is_refrigerated": container.is_refrigerated,
            "velocity_1": container.velocity_1,
            "velocity_2": container.velocity_2,
            "velocity_3": container.velocity_3,
            "input_weight": container.input_weight,
            "output_weight": container.output_weight,
            "distance_1": container.distance_1,
            "distance_2": container.distance_2,
            "distance_3": container.distance_3,
        }
    )
    for key, value in computed.items():
        setattr(container, key, value)

    db.commit()
    db.refresh(container)

    details = f"Biển xe: {container.license_plate}, CO₂e: {container.e_total:.2f} tấn, Lý do: {str(reason).strip()}"
    container_activity_service.record_activity(
        db,
        actor,
        "Sửa dữ liệu container",
        details,
    )

    return {
        "ok": True,
        "id": container.id,
        "license_plate": container.license_plate,
        "e_total": container.e_total,
    }


def delete_container(
    container_id: int,
    db: Session,
    actor: str = "system",
) -> Dict[str, Any]:
    """Delete container record"""
    container = db.query(Container).filter(Container.id == container_id).first()
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container not found",
        )

    plate = container.license_plate
    db.delete(container)
    db.commit()

    container_activity_service.record_activity(
        db,
        actor,
        "Xóa dữ liệu container",
        f"Biển xe: {plate}",
    )

    return {"ok": True, "deleted_id": container_id}


def get_scope3_summary(db: Session) -> Dict[str, Any]:
    """Get Scope 3 emissions summary (chỉ xe container)."""
    containers = db.query(Container).all()

    if not containers:
        return {
            "total_co2": 0.0,
            "total_trips": 0,
            "avg_co2_per_trip": 0.0,
            "count": 0,
            "total_distance": 0.0,
        }

    total_co2 = sum(c.e_total for c in containers)
    total_distance = sum((c.distance_1 + c.distance_2 + c.distance_3) for c in containers)
    total_trips = len(containers)
    count = len(containers)

    return {
        "total_co2": round(total_co2, 2),
        "total_distance": round(total_distance, 2),
        "count": count,
        "total_trips": total_trips,
        "avg_co2_per_trip": round(total_co2 / count, 2) if count else 0.0,
    }
