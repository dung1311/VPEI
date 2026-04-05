# services/scope3_period_service.py
"""Tổng hợp phát thải Scope 3 theo kỳ — dùng chung dashboard & API để số khớp trang Scope 3."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from services import container_service, ship_service, scope3_other_vehicle_service


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


def parse_other_vehicle_period(period: Optional[str]) -> Optional[Tuple[int, Optional[int]]]:
    """(year, month) hoặc (year, None) nếu chỉ có năm; None nếu không parse được."""
    if period is None or not str(period).strip():
        return None
    p = str(period).strip()
    for fmt in ("%Y-%m", "%Y/%m", "%m/%Y", "%d/%m/%Y"):
        try:
            d = datetime.strptime(p, fmt)
            return (d.year, d.month)
        except ValueError:
            continue
    try:
        y = int(p)
        if 1990 <= y <= 2100:
            return (y, None)
    except ValueError:
        pass
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


def other_row_in_period(row: Dict[str, Any], year: int, mf: Optional[Set[int]]) -> bool:
    parsed = parse_other_vehicle_period(row.get("period"))
    if not parsed:
        return False
    y, mo = parsed
    if y != year:
        return False
    if mf is None:
        return True
    if mo is None:
        return False
    return mo in mf


def trend_month_for_other(row: Dict[str, Any], year: int) -> Optional[int]:
    parsed = parse_other_vehicle_period(row.get("period"))
    if not parsed:
        return None
    y, mo = parsed
    if y != year:
        return None
    if mo is not None:
        return mo
    return 1


def compute_scope3_period(
    db: Session,
    year: int,
    month: Optional[int] = None,
    quarter: Optional[int] = None,
) -> Dict[str, Any]:
    """
    truck_co2: chỉ xe container (bảng Container).
    other_vehicle_co2: bản ghi scope3_other_vehicles.
    container_co2e: truck + other (khớp KPI «Xe» trên UI Scope 3 khi gộp other vào truck).
    """
    mf = month_filter_set(month, quarter)
    containers = container_service.get_all_containers(db)
    ships = ship_service.get_all_ships(db)
    others = scope3_other_vehicle_service.get_all_other_vehicle_records(db)

    truck_co2 = 0.0
    other_ve_co2 = 0.0
    ship_co2 = 0.0
    s3_trend = [0.0] * 12
    truck_trend = [0.0] * 12
    ship_trend = [0.0] * 12
    other_trend = [0.0] * 12
    n_cont = 0
    n_ship = 0
    n_other = 0

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

    for o in others:
        if not other_row_in_period(o, year, mf):
            continue
        val = float(o.get("e_total") or 0.0)
        other_ve_co2 += val
        n_other += 1
        tm = trend_month_for_other(o, year)
        if tm is not None and 1 <= tm <= 12:
            s3_trend[tm - 1] += val
            other_trend[tm - 1] += val

    container_co2e = truck_co2 + other_ve_co2
    total = container_co2e + ship_co2

    container_trend = [truck_trend[i] + other_trend[i] for i in range(12)]

    return {
        "truck_co2e": truck_co2,
        "other_vehicle_co2e": other_ve_co2,
        "container_co2e": container_co2e,
        "ship_co2e": ship_co2,
        "total_co2e": total,
        "record_count": n_cont + n_ship + n_other,
        "n_containers": n_cont,
        "n_ships": n_ship,
        "n_other_vehicles": n_other,
        "trend_monthly": s3_trend,
        "trend_container_monthly": container_trend,
        "trend_ship_monthly": ship_trend,
        "containers": containers,
        "ships": ships,
    }
