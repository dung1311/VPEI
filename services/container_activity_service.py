from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.audit_log import AuditLog


def _normalize_detail_dates(detail: str) -> str:
    text = detail or ""

    def _replace(match: re.Match[str]) -> str:
        raw = match.group(0)
        try:
            return datetime.strptime(raw, "%Y-%m-%dT%H:%M").strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return raw

    return re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", _replace, text)


def _activity_type(action: str) -> str:
    text = (action or "").strip().lower()
    if "xóa" in text or "delete" in text:
        return "del"
    if "sửa" in text or "cập nhật" in text or "update" in text:
        return "edit"
    if "xuất" in text or "report" in text or "export" in text:
        return "report"
    return "add"


def record_activity(
    db: Session,
    username: str,
    action: str,
    description: Optional[str] = None,
) -> AuditLog:
    from models.user import vn_now

    now = vn_now()
    audit = AuditLog(
        username=(username or "system").strip() or "system",
        action=action,
        description=description,
        month_year=now.strftime("%m/%Y"),
        scope="scope3",
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def get_scope3_activity_history(
    db: Session,
    year: Optional[int] = None,
    month: Optional[int] = None,
    quarter: Optional[int] = None,
) -> Dict[str, Any]:
    query = db.query(AuditLog).filter(AuditLog.scope == "scope3")

    if year and month:
        query = query.filter(AuditLog.month_year == f"{month:02d}/{year}")
    elif year and quarter:
        q = int(quarter)
        mlist = list(range((q - 1) * 3 + 1, q * 3 + 1))
        patterns = [f"{m:02d}/{year}" for m in mlist]
        query = query.filter(AuditLog.month_year.in_(patterns))
    elif year:
        query = query.filter(AuditLog.month_year.like(f"%/{year}"))

    logs_db = query.order_by(AuditLog.created_at.desc()).all()
    month_year_values = [
        row[0]
        for row in db.query(AuditLog.month_year)
        .filter(AuditLog.scope == "scope3")
        .distinct()
        .all()
        if row[0]
    ]

    def month_year_key(v: str) -> tuple[int, int]:
        try:
            m_text, y_text = v.split("/")
            return (int(y_text), int(m_text))
        except Exception:
            return (0, 0)

    month_year_values.sort(key=month_year_key, reverse=True)

    years = sorted(
        {
            int(v.split("/")[1])
            for v in month_year_values
            if "/" in v and v.split("/")[1].isdigit()
        },
        reverse=True,
    )

    logs: List[Dict[str, Any]] = []
    for log in logs_db:
        logs.append(
            {
                "id": log.id,
                "user": log.username,
                "type": _activity_type(log.action),
                "action": log.action,
                "detail": _normalize_detail_dates(log.description or ""),
                "time": log.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "month_year": log.month_year,
            }
        )

    return {
        "logs": logs,
        "available_month_year": month_year_values,
        "available_years": years,
    }


def delete_scope3_activity(db: Session, activity_id: int) -> Dict[str, Any]:
    target = db.query(AuditLog).filter(AuditLog.id == activity_id, AuditLog.scope == "scope3").first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    db.delete(target)
    db.commit()
    return {"ok": True, "deleted_id": activity_id}
