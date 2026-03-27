# routers/scope1_dashboard.py
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from core.database import get_db
from services.scope1_dashboard import Scope1DashboardService
from services.scope1_emission_source import DashboardService as StatusService

router = APIRouter(prefix="/scope1", tags=["Scope 1 Dashboard"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
@router.get("", response_class=HTMLResponse)
def render_dashboard(request: Request, year: int = Query(None), month: int = Query(None), db: Session = Depends(get_db)):
    now = datetime.now()
    curr_year = year or now.year
    curr_month = month or now.month
    
    dashboard_data = Scope1DashboardService.get_dashboard_data(db, curr_year, curr_month)
    period_info = StatusService.get_period_summary(db, curr_year, curr_month)

    return templates.TemplateResponse("scope/scope_01_dashboard.html", {
        "request": request,
        "current_year": curr_year,
        "current_month": curr_month,
        "status": period_info["status"].value if period_info["status"] else "Draft",
        "data": dashboard_data
    })

@router.get("/dashboard/export/excel")
def export_dashboard_excel(year: int, month: int, db: Session = Depends(get_db)):
    excel_file = Scope1DashboardService.export_excel(db, year, month)
    return StreamingResponse(
        excel_file, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        headers={"Content-Disposition": f"attachment; filename=VPEI_Scope1_{month}_{year}.xlsx"}
    )