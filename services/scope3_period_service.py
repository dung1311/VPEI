# services/scope3_period_service.py
"""Tổng hợp phát thải Scope 3 theo kỳ — dùng chung dashboard & API để số khớp trang Scope 3."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from services import (
    container_service,
    harbor_craft_service,
    ship_service,
)


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
    container_co2e: xe container (bảng Container).
    other_vehicle_co2e / n_other_vehicles luôn 0 (đã bỏ bảng PT khác).
    """
    mf = month_filter_set(month, quarter)
    containers = container_service.get_all_containers(db)
    ships = ship_service.get_all_ships(db)

    truck_co2 = 0.0
    other_ve_co2 = 0.0
    ship_co2 = 0.0
    harbor_co2 = 0.0
    s3_trend = [0.0] * 12
    truck_trend = [0.0] * 12
    ship_trend = [0.0] * 12
    other_trend = [0.0] * 12
    harbor_trend = [0.0] * 12
    n_cont = 0
    n_ship = 0
    n_other = 0
    n_harbor = 0

    for c in containers:
        if not row_in_period_start_time(c.get("start_time"), year, mf):
            continue
        val = _co2_container_row(c)
        truck_co2 += val
        n_cont += 1
        dt = parse_datetime(c.get("start_time"))
        if dt:
            s3_trend[dt.month - 1] += val
            truck_trend[dt.month - 1] += val

    for s in ships:
        if not row_in_period_start_time(getattr(s, "start_time", None), year, mf):
            continue
        val = _co2_ship(s)
        ship_co2 += val
        n_ship += 1
        dt = parse_datetime(getattr(s, "start_time", None))
        if dt:
            s3_trend[dt.month - 1] += val
            ship_trend[dt.month - 1] += val

    harbors = harbor_craft_service.get_all_harbor_crafts(db)
    for h in harbors:
        if not row_in_period_start_time(h.get("record_time"), year, mf):
            continue
        val = float(h.get("e_total") or 0.0)
        harbor_co2 += val
        n_harbor += 1
        dt = parse_datetime(h.get("record_time"))
        if dt:
            s3_trend[dt.month - 1] += val
            harbor_trend[dt.month - 1] += val

    container_co2e = truck_co2 + other_ve_co2
    total = container_co2e + ship_co2 + harbor_co2

    container_trend = [truck_trend[i] + other_trend[i] for i in range(12)]

    return {
        "truck_co2e": truck_co2,
        "other_vehicle_co2e": other_ve_co2,
        "container_co2e": container_co2e,
        "ship_co2e": ship_co2,
        "total_co2e": total,
        "record_count": n_cont + n_ship + n_other + n_harbor,
        "n_containers": n_cont,
        "n_ships": n_ship,
        "n_other_vehicles": n_other,
        "n_harbor_crafts": n_harbor,
        "harbor_co2e": harbor_co2,
        "trend_monthly": s3_trend,
        "trend_container_monthly": container_trend,
        "trend_ship_monthly": ship_trend,
        "trend_harbor_monthly": harbor_trend,
        "containers": containers,
        "ships": ships,
    }


def _metric_from_payload(p: Dict[str, Any], key: str) -> float:
    if key == "total":
        return float(p.get("total_co2e") or 0.0)
    if key == "container":
        return float(p.get("container_co2e") or 0.0)
    if key == "ship":
        return float(p.get("ship_co2e") or 0.0)
    if key == "harbor":
        return float(p.get("harbor_co2e") or 0.0)
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
            "harbor": pack("harbor"),
        },
    }
