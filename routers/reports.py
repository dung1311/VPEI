from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from core.database import get_db
from services.report_service import ReportService


def _parse_iso_date(s: Optional[str]) -> Optional[date]:
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    try:
        return datetime.strptime(t[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="date_start/date_end phải là YYYY-MM-DD")

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="templates")

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def get_report_page(request: Request):
    return templates.TemplateResponse("reports/reports.html", {"request": request})

@router.get("/download")
async def download_report(
    request: Request,
    year: int = Query(2023),
    month: int = Query(None),
    quarter: int = Query(None),
    date_start: str = Query(None),
    date_end: str = Query(None),
    include_appendix: bool = Query(True),
    db: Session = Depends(get_db),
):
    """
    Download the generated report as a Word document.
    Nếu có cả date_start và date_end (YYYY-MM-DD), báo cáo lọc theo khoảng ngày đó.
    """
    ds = _parse_iso_date(date_start)
    de = _parse_iso_date(date_end)
    if (ds is None) ^ (de is None):
        raise HTTPException(status_code=400, detail="Cần gửi cả date_start và date_end, hoặc không gửi cả hai")
    if ds is not None and de is not None and ds > de:
        raise HTTPException(status_code=400, detail="date_start phải trước hoặc bằng date_end")

    try:
        report_bytes = ReportService.generate_vpei_final_report(
            db,
            year,
            month=month,
            quarter=quarter,
            date_start=ds,
            date_end=de,
            include_appendix=include_appendix,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if ds is not None and de is not None:
        tag = f"{ds.strftime('%Y%m%d')}_{de.strftime('%Y%m%d')}"
    elif month is not None:
        tag = f"{year}_T{month}"
    elif quarter is not None:
        tag = f"{year}_Q{quarter}"
    else:
        tag = f"{year}"

    return StreamingResponse(
        iter([report_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=VPEI_Report_{tag}.docx"},
    )
