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
    return "add"

def record_activity(
    db: Session,
    username: str,
    action: str,
    description: Optional[str] = None,
) -> AuditLog:
    now = datetime.now()
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