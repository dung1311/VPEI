import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import extract
from datetime import datetime

from core.database import get_db
from models.audit_log import AuditLog
from models.device import ActivityData
from models.ship import Ship
from models.container import Container
from models.electrical_item import ElectricalItem

router = APIRouter()

@router.get("/api/common/periods")
def get_common_periods(db: Session = Depends(get_db)):
    years = set()
    
    default_year = datetime.now().year
    default_month = datetime.now().month
    
    try:
        # Scope 1 (ActivityData period_year)
        s1_years = db.query(ActivityData.period_year).distinct().all()
        for y in s1_years:
            if y[0]: years.add(int(y[0]))
            
        latest_act = db.query(ActivityData).order_by(ActivityData.period_year.desc(), ActivityData.period_month.desc()).first()
        if latest_act:
            default_year = latest_act.period_year
            default_month = latest_act.period_month
            
        # Scope 3 AuditLogs (month_year: MM/YYYY)
        s3_logs = db.query(AuditLog.month_year).distinct().all()
        for row in s3_logs:
            if row[0] and "/" in row[0]:
                try:
                    y = int(row[0].split("/")[1])
                    years.add(y)
                except ValueError:
                    pass
        
        # Scope 3 (Ship & Container start_time)
        ships_y = db.query(extract('year', Ship.start_time)).distinct().all()
        for y in ships_y:
            if y[0]: years.add(int(y[0]))
            
        conts_y = db.query(extract('year', Container.start_time)).distinct().all()
        for y in conts_y:
            if y[0]: years.add(int(y[0]))

        # Scope 2 — electrical_items.period_value (vd: 2025-06-15, 15/06/2025, "Tháng 06 - 2025")
        s2_vals = db.query(ElectricalItem.period_value).distinct().all()
        for row in s2_vals:
            pv = (row[0] or "").strip()
            if not pv:
                continue
            parsed = None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    parsed = datetime.strptime(pv, fmt)
                    break
                except ValueError:
                    continue
            if parsed:
                years.add(parsed.year)
            else:
                for m in re.finditer(r"\b(19|20)\d{2}\b", pv):
                    years.add(int(m.group(0)))

    except Exception as e:
        print("Lỗi khi fetch period years:", e)

    if not years:
        years.add(datetime.now().year)
        
    # Thêm luôn năm kế tiếp và năm trước (để UX dễ chọn)
    sorted_years = sorted(list(years), reverse=True)
    if datetime.now().year not in sorted_years:
        sorted_years.insert(0, datetime.now().year)

    default_quarter = (default_month - 1) // 3 + 1

    return {
        "years": sorted_years,
        "quarters": [
            {"id": 1, "name": "Quý 1 (T1-T3)"}, 
            {"id": 2, "name": "Quý 2 (T4-T6)"}, 
            {"id": 3, "name": "Quý 3 (T7-T9)"}, 
            {"id": 4, "name": "Quý 4 (T10-T12)"}
        ],
        "months": [{"id": i, "name": f"Tháng {i}"} for i in range(1, 13)],
        "default_year": default_year,
        "default_month": default_month,
        "default_quarter": default_quarter
    }
