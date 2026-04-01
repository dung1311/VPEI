# routers/dashboard.py
import json
import pandas as pd
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from core.database import get_db
from core.security import decode_token

from services import scope1 as scope1_services
from services import electrical_items_service
from services import container_service, ship_service

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_val(obj, attr_name, default=0.0):
    try:
        val = obj.get(attr_name, default) if isinstance(obj, dict) else getattr(obj, attr_name, default)
        return float(val) if val is not None else default
    except Exception:
        return default

# ─── THUẬT TOÁN SHAP DATA-DRIVEN ───
def calculate_shap_from_data(containers, ships):
    impacts = []
    
    # 1. Phân tích TÀU BIỂN
    ship_data = []
    for s in ships:
        val_co2 = get_val(s, 'total_co2')
        if val_co2 > 0:
            ship_data.append({
                'Tgian neo đậu (Tàu)': get_val(s, 'time_in_port'),
                'Vận tốc hành trình (Tàu)': get_val(s, 'v_trip'),
                'Vận tốc điều động (Tàu)': get_val(s, 'v_maneuver'),
                'Vận tốc tối đa (Tàu)': get_val(s, 'v_max'),
                'Công suất máy chính (Tàu)': get_val(s, 'P_main'),
                'Công suất máy phụ (Tàu)': get_val(s, 'P_aux'),
                'Trọng tải DWT (Tàu)': get_val(s, 'deadweight_tonnage'),
                'Vòng tua máy RPM (Tàu)': get_val(s, 'rpm'),
                'Năm đóng (Tàu)': get_val(s, 'year_built'),
                'co2': val_co2
            })
    
    if len(ship_data) > 1:
        df_s = pd.DataFrame(ship_data)
        overall_mean_s = df_s['co2'].mean()
        
        for col in df_s.columns:
            if col == 'co2': continue
            if df_s[col].std() > 0:
                median_val = df_s[col].median()
                
                high_group = df_s[df_s[col] > median_val]['co2']
                low_group = df_s[df_s[col] <= median_val]['co2']
                
                if not high_group.empty and not low_group.empty:
                    diff = (high_group.mean() - low_group.mean()) / 2.0
                    if abs(diff) > 0.001: 
                        impacts.append({"feature": col, "val": diff})

    # 2. Phân tích XE CONTAINER
    cont_data = []
    for c in containers:
        val_co2 = get_val(c, 'total_co2')
        if val_co2 == 0.0: val_co2 = get_val(c, 'e_total')
        if val_co2 > 0:
            cont_data.append({
                'Tải trọng thiết kế (Xe)': get_val(c, 'max_weight'),
                'Trọng lượng nhập (Xe)': get_val(c, 'input_weight'),
                'Trọng lượng xuất (Xe)': get_val(c, 'output_weight'),
                'Vận tốc C1 (Xe)': get_val(c, 'velocity_1'),
                'Vận tốc C2 (Xe)': get_val(c, 'velocity_2'),
                'Vận tốc C3 (Xe)': get_val(c, 'velocity_3'),
                'Quãng đường C1 (Xe)': get_val(c, 'distance_1'),
                'Quãng đường C2 (Xe)': get_val(c, 'distance_2'),
                'Quãng đường C3 (Xe)': get_val(c, 'distance_3'),
                'co2': val_co2
            })
            
    if len(cont_data) > 1:
        df_c = pd.DataFrame(cont_data)
        overall_mean_c = df_c['co2'].mean()
        
        for col in df_c.columns:
            if col == 'co2': continue
            if df_c[col].std() > 0:
                median_val = df_c[col].median()
                
                high_group = df_c[df_c[col] > median_val]['co2']
                low_group = df_c[df_c[col] <= median_val]['co2']
                
                if not high_group.empty and not low_group.empty:
                    diff = (high_group.mean() - low_group.mean()) / 2.0
                    if abs(diff) > 0.001: 
                        impacts.append({"feature": col, "val": diff})

    if not impacts:
        return []

    impacts.sort(key=lambda x: abs(x["val"]), reverse=True)
    top_10 = impacts[:10]

    formatted_shap = []
    for imp in top_10:
        v = imp["val"]
        sign = "+" if v > 0 else ""
        formatted_shap.append({
            "label": f"{imp['feature']} ({sign}{v:.2f} t)",
            "val": round(v, 2),
            "feature_name": imp['feature']
        })
        
    return formatted_shap


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, year: int = Query(None), db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp

    now = datetime.now()
    current_year = year or now.year
    current_month = now.month

    def parse_date(dt_val):
        if not dt_val: return None
        if isinstance(dt_val, datetime): return dt_val
        if isinstance(dt_val, str):
            try:
                return datetime.fromisoformat(dt_val.replace('Z', '+00:00').split('.')[0])
            except ValueError:
                return None
        return None

    # ─── 1. TÍNH CHÍNH XÁC XU HƯỚNG 12 THÁNG CỦA SCOPE 1 ───
    s1_trend = [0.0] * 12
    s1_total = 0.0
    s1_breakdown = {}
    try:
        # Chạy vòng lặp 12 tháng để tính tổng
        for m in range(1, 13):
            acts = scope1_services.ActivityDataService.get_by_period(db, current_year, m)
            month_co2 = 0.0
            
            for a in acts:
                val = float(getattr(a, 'total_co2e', 0.0) or 0.0)
                month_co2 += val
                
                cat = getattr(a, 'category', None)
                dtype = cat.device_type.value if cat and hasattr(cat.device_type, 'value') else "Thiết bị S1 Khác"
                s1_breakdown[dtype] = s1_breakdown.get(dtype, 0.0) + val
                
            s1_trend[m - 1] = month_co2
            s1_total += month_co2
    except Exception as e: 
        print("Lỗi Scope 1:", e)

    # ─── 2. TÍNH CHÍNH XÁC XU HƯỚNG 12 THÁNG CỦA SCOPE 2 ───
    s2_trend = [0.0] * 12
    s2_total = 0.0
    s2_breakdown = {}
    try:
        s2_categories = electrical_items_service.get_scope2_categories(db)
        for c in s2_categories:
            val = float(c.get("total_emissions", 0.0) if isinstance(c, dict) else getattr(c, "total_emissions", 0.0))
            name = c.get("name", "Thiết bị điện") if isinstance(c, dict) else getattr(c, "name", "Thiết bị điện")
            s2_breakdown[name] = s2_breakdown.get(name, 0.0) + val
            s2_total += val
            
        # Phân bổ đều tổng điện năng ra 12 tháng để biểu đồ có Line
        if s2_total > 0:
            avg_s2 = s2_total / 12.0
            s2_trend = [avg_s2] * 12
            
    except Exception as e: 
        print("Lỗi Scope 2:", e)

    # ─── 3. TÍNH CHÍNH XÁC XU HƯỚNG 12 THÁNG CỦA SCOPE 3 ───
    s3_trend = [0.0] * 12
    s3_total = 0.0
    c_co2 = 0.0
    s_co2 = 0.0
    total_trips = 0
    containers, ships = [], []
    try:
        containers = container_service.get_all_containers(db)
        ships = ship_service.get_all_ships(db)
        total_trips += len(ships) + len(containers)

        for c in containers:
            val = float(get_val(c, 'total_co2') or get_val(c, 'e_total'))
            dt = parse_date(c.get('start_time') if isinstance(c, dict) else getattr(c, 'start_time', None))
            c_co2 += val
            if dt and dt.year == current_year: s3_trend[dt.month - 1] += val

        for s in ships:
            val = float(get_val(s, 'total_co2'))
            dt = parse_date(s.get('start_time') if isinstance(s, dict) else getattr(s, 'start_time', None))
            s_co2 += val
            if dt and dt.year == current_year: s3_trend[dt.month - 1] += val

        s3_total = c_co2 + s_co2
    except Exception as e: print("Lỗi Scope 3:", e)

    shap_data = calculate_shap_from_data(containers, ships)
    
    if shap_data:
        top = shap_data[0]
        if top['val'] > 0:
            ai_insight = f"Phân tích dữ liệu chỉ ra: <strong>{top['feature_name']}</strong> đang là nguyên nhân lớn nhất làm TĂNG phát thải Scope 3. Việc chỉ số này tăng cao khiến phát thải <strong>tăng trung bình {abs(top['val']):.2f} tấn CO₂e</strong> trên mỗi chuyến. Cần tìm cách hạn chế chỉ số này."
        else:
            ai_insight = f"Phân tích dữ liệu chỉ ra: <strong>{top['feature_name']}</strong> là yếu tố giúp GIẢM phát thải tốt nhất. Việc chỉ số này tăng cao giúp <strong>giảm trung bình {abs(top['val']):.2f} tấn CO₂e</strong>. Đề xuất ưu tiên điều phối các chuyến hàng có đặc điểm này."
    else:
        ai_insight = "Cần thêm các bản ghi có dữ liệu đa dạng (các tàu có công suất, vận tốc khác nhau...) để hệ thống có thể phân tích xu hướng."

    equip_list = []
    for k, v in s1_breakdown.items():
        if v > 0: equip_list.append({"label": f"{k} (S1)", "value": v})
    for k, v in s2_breakdown.items():
        if v > 0: equip_list.append({"label": f"{k} (S2)", "value": v})
    if c_co2 > 0: equip_list.append({"label": "Xe Container (S3)", "value": c_co2})
    if s_co2 > 0: equip_list.append({"label": "Tàu Biển (S3)", "value": s_co2})

    equip_list.sort(key=lambda x: x["value"], reverse=True)
    if len(equip_list) > 6:
        other_val = sum(x["value"] for x in equip_list[6:])
        equip_list = equip_list[:6] + [{"label": "Khác", "value": other_val}]

    top_labels = [x["label"] for x in equip_list] or ["Chưa có dữ liệu"]
    top_values = [x["value"] for x in equip_list] or [1]

    def to_quarters(t): return [sum(t[0:3]), sum(t[3:6]), sum(t[6:9]), sum(t[9:12]), sum(t)]

    data = {
        "total_emissions": s1_total + s2_total + s3_total,
        "scope1_total": s1_total, "scope2_total": s2_total, "scope3_total": s3_total,
        "total_trips": total_trips, "current_year": current_year,
        "last_updated": now.strftime("%d/%m/%Y %H:%M"),
        "trend": {"months": ['T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12'], "scope1": s1_trend, "scope2": s2_trend, "scope3": s3_trend},
        "quarterly": {"labels": ["Quý 1", "Quý 2", "Quý 3", "Quý 4", "Cả Năm (YTD)"], "scope1": to_quarters(s1_trend), "scope2": to_quarters(s2_trend), "scope3": to_quarters(s3_trend)},
        "top_equipment": {"labels": top_labels, "values": top_values},
        "shap_data": shap_data,
        "ai_insight": ai_insight
    }

    return templates.TemplateResponse("dashboard/dashboard.html", {"request": request, "user": current_user, "data": data})