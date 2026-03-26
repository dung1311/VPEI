# routers/frontend.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Frontend Views"])

# Cấu hình đường dẫn trỏ tới thư mục chứa file HTML của bạn
templates = Jinja2Templates(directory="templates")

@router.get("/scope1-emission-source-test", response_class=HTMLResponse)
def render_scope1_dashboard(request: Request):
    
    # 1. TẠO DỮ LIỆU GIẢ LẬP (MOCK DATA) ĐỂ TRUYỀN VÀO TEMPLATE
    # Sau này bạn có thể thay thế bằng hàm db.query() từ Database
    mock_categories = [
        {"name": "OOG Mobile Crane", "count": 12, "total_emissions": "8,540"},
        {"name": "Reach Stacker", "count": 15, "total_emissions": "10,200"},
        {"name": "Terberg", "count": 8, "total_emissions": "4,500"},
        {"name": "Forklift", "count": 20, "total_emissions": "6,800"}
    ]
    
    mock_activities = [
        {"device_name": "OOG Mobile Crane", "power": 500, "hours": 120, "lf": 0.75, "total_co2": 320.5},
        {"device_name": "Reach Stacker", "power": 350, "hours": 150, "lf": 0.80, "total_co2": 378.2}
    ]

    # 2. RENDER TEMPLATE KÈM DỮ LIỆU
    return templates.TemplateResponse(
        "scope/scope_01_emission_source.html", # Đường dẫn tương đối từ thư mục templates
        {
            "request": request, # Tham số bắt buộc của Jinja2 trong FastAPI
            "current_year": 2026,
            "current_month": "02",
            "status": "Draft",
            "categories": mock_categories,
            "activities": mock_activities,
            "total_scope1_co2": "42,500"
        }
    )