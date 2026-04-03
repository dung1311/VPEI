from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from core.database import get_db
from services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="templates")

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def get_report_page(request: Request):
    return templates.TemplateResponse("reports/reports.html", {"request": request})

@router.get("/download")
async def download_report(request: Request, year: int = Query(2023), db: Session = Depends(get_db)):
    """
    Download the generated report as a Word document.
    """
    report_bytes = ReportService.generate_vpei_final_report(db, year)
    return StreamingResponse(
        iter([report_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=VPEI_Report_{year}.docx"}
    )
