# services/scope3_period_service.py
"""Tổng hợp phát thải Scope 3 theo kỳ — dùng chung dashboard & API để số khớp trang Scope 3."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import extract, and_, or_, func

from models.container import Container
from models.ship import Ship
from models.harbor_craft import HarborCraft
from models.other_vehicle import OtherVehicle
from models.ship_voyage import ShipVoyage

from services import (
    container_service,
    harbor_craft_service,
    ship_service,
)


def _get_period_filters(model, date_column, year: int, month: Optional[int], quarter: Optional[int]):
    filters = [extract('year', date_column) == year]
    if month is not None:
        filters.append(extract('month', date_column) == int(month))
    elif quarter is not None:
        q = int(quarter)
        filters.append(and_(
            extract('month', date_column) >= (q - 1) * 3 + 1,
            extract('month', date_column) <= q * 3
        ))
    return filters


def month_filter_set(month: Optional[int], quarter: Optional[int]) -> Optional[Set[int]]:
    if month is not None:
        return {int(month)}
    if quarter is not None:
        q = int(quarter)
        return set(range((q - 1) * 3 + 1, q * 3 + 1))
    return None


def parse_datetime(dt_val: Any) -> Optional[datetime]:
    if not dt_val:
        return None
    if isinstance(dt_val, datetime):
        return dt_val
    if isinstance(dt_val, str):
        try:
            return datetime.fromisoformat(dt_val.replace("Z", "+00:00").split(".")[0])
        except ValueError:
            return None
    return None


def _co2_container_row(c: Dict[str, Any]) -> float:
    tc = c.get("total_co2")
    if tc is not None:
        try:
            v = float(tc)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    try:
        return float(c.get("e_total") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _co2_ship(s: Any) -> float:
    v = getattr(s, "total_co2", None)
    if v is not None:
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def row_in_period_start_time(
    start_time: Any,
    year: int,
    mf: Optional[Set[int]],
) -> bool:
    dt = parse_datetime(start_time)
    if not (dt and dt.year == year):
        return False
    if mf is not None and dt.month not in mf:
        return False
    return True


def compute_scope3_period(
    db: Session,
    year: int,
    month: Optional[int] = None,
    quarter: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Otimized DB-level filtering and computation.
    """
    from services import equipment_service

    cont_filters = _get_period_filters(Container, Container.start_time, year, month, quarter)
    containers = db.query(Container).filter(*cont_filters).all()
    
    ship_filters = _get_period_filters(Ship, Ship.start_time, year, month, quarter)
    ships = db.query(Ship).filter(*ship_filters).all()

    harbor_filters = _get_period_filters(HarborCraft, HarborCraft.record_time, year, month, quarter)
    harbor_crafts = db.query(HarborCraft).filter(*harbor_filters).all()

    other_filters = _get_period_filters(OtherVehicle, OtherVehicle.record_time, year, month, quarter)
    other_vehicles = db.query(OtherVehicle).filter(*other_filters).all()

    voyage_filters = _get_period_filters(ShipVoyage, ShipVoyage.start_time, year, month, quarter)
    ship_voyages = db.query(ShipVoyage).filter(*voyage_filters).all()
    equipment_summary = equipment_service.summary_by_scope(db, 3, year=year, month=month, quarter=quarter)

    truck_co2 = 0.0
    other_ve_co2 = 0.0
    ship_co2 = 0.0
    voyage_co2 = 0.0
    harbor_co2 = 0.0
    s3_trend = [0.0] * 12
    truck_trend = [0.0] * 12
    ship_trend = [0.0] * 12
    voyage_trend = [0.0] * 12
    other_trend = [0.0] * 12
    harbor_trend = [0.0] * 12
    equipment_trend = [float(v or 0.0) for v in equipment_summary["monthly_totals"]]
    
    n_cont = len(containers)
    n_ship = len(ships)
    n_voyage = len(ship_voyages)
    n_other = len(other_vehicles)
    n_harbor = len(harbor_crafts)

    for c in containers:
        val = _co2_container_row(c.__dict__)
        truck_co2 += val
        
        # start_time may be a datetime object or string. For models, it is usually datetime.
        dt = getattr(c, "start_time", None)
        if dt:
            m_idx = dt.month - 1
            s3_trend[m_idx] += val
            truck_trend[m_idx] += val

    for s in ships:
        val = getattr(s, "total_co2", 0.0) or 0.0
        ship_co2 += val
        
        dt = getattr(s, "start_time", None)
        if dt:
            m_idx = dt.month - 1
            s3_trend[m_idx] += val
            ship_trend[m_idx] += val

    for sv in ship_voyages:
        val = getattr(sv, "total_co2", 0.0) or 0.0
        voyage_co2 += val
        
        dt = getattr(sv, "start_time", None)
        if dt:
            m_idx = dt.month - 1
            s3_trend[m_idx] += val
            voyage_trend[m_idx] += val

    for h in harbor_crafts:
        val = getattr(h, "e_total", 0.0) or 0.0
        harbor_co2 += val
        
        dt = getattr(h, "record_time", None)
        if dt:
            m_idx = dt.month - 1
            s3_trend[m_idx] += val
            harbor_trend[m_idx] += val

    for ov in other_vehicles:
        val = getattr(ov, "e_total", 0.0) or 0.0
        other_ve_co2 += val

        dt = getattr(ov, "record_time", None)
        if dt:
            m_idx = dt.month - 1
            s3_trend[m_idx] += val
            other_trend[m_idx] += val

    container_co2e = truck_co2
    equipment_co2 = float(equipment_summary["total_co2e"] or 0.0)
    total = container_co2e + ship_co2 + voyage_co2 + harbor_co2 + other_ve_co2 + equipment_co2
    s3_trend = [s3_trend[idx] + equipment_trend[idx] for idx in range(12)]

    container_trend = truck_trend[:]

    return {
        "truck_co2e": truck_co2,
        "other_vehicle_co2e": other_ve_co2,
        "container_co2e": container_co2e,
        "ship_co2e": ship_co2,
        "voyage_co2e": voyage_co2,
        "equipment_co2e": equipment_co2,
        "total_co2e": total,
        "record_count": n_cont + n_ship + n_voyage + n_other + n_harbor + len(equipment_summary["records"]),
        "n_containers": n_cont,
        "n_ships": n_ship,
        "n_voyages": n_voyage,
        "n_other_vehicles": n_other,
        "n_harbor_crafts": n_harbor,
        "harbor_co2e": harbor_co2,
        "trend_monthly": s3_trend,
        "trend_container_monthly": container_trend,
        "trend_ship_monthly": ship_trend,
        "trend_voyage_monthly": voyage_trend,
        "trend_harbor_monthly": harbor_trend,
        "trend_other_vehicle_monthly": other_trend,
        "trend_equipment_monthly": equipment_trend,
        "containers": [c.__dict__ for c in containers], # ensure dict format for existing UI
        "ships": [s.__dict__ for s in ships], # ensure dict format for existing UI
        "voyages": [sv.__dict__ for sv in ship_voyages], # ensure dict format for existing UI
    }


def _metric_from_payload(p: Dict[str, Any], key: str) -> float:
    if key == "total":
        return float(p.get("total_co2e") or 0.0)
    if key == "container":
        return float(p.get("container_co2e") or 0.0)
    if key == "ship":
        return float(p.get("ship_co2e") or 0.0)
    if key == "voyage":
        return float(p.get("voyage_co2e") or 0.0)
    if key == "harbor":
        return float(p.get("harbor_co2e") or 0.0)
    if key == "other_vehicle":
        return float(p.get("other_vehicle_co2e") or 0.0)
    if key == "equipment":
        return float(p.get("equipment_co2e") or 0.0)
    return 0.0


def _series_with_pct(values: List[float]) -> Dict[str, Any]:
    pct: List[float] = [0.0]
    for i in range(1, len(values)):
        a, b = values[i - 1], values[i]
        pct.append(round(((b - a) / a) * 100, 1) if a else 0.0)
    return {"values": values, "pct_vs_prev": pct}


def build_scope3_comparison_payload(
    db: Session,
    year: int,
    month: Optional[int] = None,
    quarter: Optional[int] = None,
) -> Dict[str, Any]:
    if month is not None:
        mode = "month"
        buckets: List[Tuple[int, Optional[int], Optional[int]]] = [(year, m, None) for m in range(1, 13)]
        labels = [f"{year}-{str(m).zfill(2)}" for m in range(1, 13)]
        display_labels = [f"T{m}" for m in range(1, 13)]
        current_index = max(0, min(int(month) - 1, 11))
    elif quarter is not None:
        mode = "quarter"
        buckets = [(year, None, q) for q in range(1, 5)]
        labels = [f"{year}-Q{q}" for q in range(1, 5)]
        display_labels = [f"Q{q}" for q in range(1, 5)]
        current_index = max(0, min(int(quarter) - 1, 3))
    else:
        mode = "year"
        years = [year - 4 + i for i in range(5)]
        buckets = [(y, None, None) for y in years]
        labels = [str(y) for y in years]
        display_labels = labels[:]
        current_index = 4 if year in years else len(years) - 1

    period_payloads = [
        compute_scope3_period(db, y, m, q) for y, m, q in buckets
    ]

    def pack(metric_key: str) -> Dict[str, Any]:
        vals = [_metric_from_payload(p, metric_key) for p in period_payloads]
        return _series_with_pct(vals)

    return {
        "mode": mode,
        "year": year,
        "labels": labels,
        "display_labels": display_labels,
        "current_index": current_index,
        "series": {
            "total": pack("total"),
            "container": pack("container"),
            "ship": pack("ship"),
            "voyage": pack("voyage"),
            "harbor": pack("harbor"),
            "other_vehicle": pack("other_vehicle"),
            "equipment": pack("equipment"),
        },
    }
