# routers/dashboard.py
import json
import pandas as pd
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Set

from core.database import get_db
from core.security import decode_token

# Import các services
from services import scope1 as scope1_services
from services import electrical_items_service
from services import scope2_activity_service
from services import container_service, ship_service

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _month_filter_set(month: Optional[int], quarter: Optional[int]) -> Optional[Set[int]]:
    if month is not None:
        return {month}
    if quarter is not None:
        q = int(quarter)
        return set(range((q - 1) * 3 + 1, q * 3 + 1))
    return None


def get_val(obj, attr_name, default=0.0):
    """Hàm phụ trợ lấy giá trị an toàn cho cả Dict và Object"""
    try:
        val = obj.get(attr_name, default) if isinstance(obj, dict) else getattr(obj, attr_name, default)
        return float(val) if val is not None else default
    except Exception:
        return default

# ─── THUẬT TOÁN SHAP CHUẨN (1 VECTOR MỖI THUỘC TÍNH) ───
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
                    # Tính chênh lệch biên (Marginal impact) - Đại diện cho: "Khi thuộc tính này CAO thì CO2 thay đổi bao nhiêu"
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

    # Sắp xếp lấy Top 10 thuộc tính có độ ảnh hưởng cực đoan nhất (âm hay dương đều lấy)
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


# ─── API HIỂN THỊ DASHBOARD ───
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    year: int = Query(None),
    quarter: int = Query(None),
    month: int = Query(None),
    db: Session = Depends(get_db),
):
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
    mf = _month_filter_set(month, quarter)
    if month is not None:
        period_label = f"Tháng {month}/{current_year}"
    elif quarter is not None:
        period_label = f"Quý {quarter}/{current_year}"
    else:
        period_label = f"Năm {current_year}"

    # Hàm parse ngày an toàn
    def parse_date(dt_val):
        if not dt_val: return None
        if isinstance(dt_val, datetime): return dt_val
        if isinstance(dt_val, str):
            try:
                # Xử lý chuỗi ISO hoặc chuỗi có định dạng chuẩn
                return datetime.fromisoformat(dt_val.replace('Z', '+00:00').split('.')[0])
            except ValueError:
                return None
        return None

    # ─── 1. SCOPE 1 ───
    s1_trend = [0.0] * 12
    s1_total = 0.0
    try:
        for m in range(1, 13):
            if mf is not None and m not in mf:
                continue
            acts = scope1_services.ActivityDataService.get_by_period(db, current_year, m)
            month_co2 = 0.0
            for a in acts:
                val = float(getattr(a, 'total_co2e', 0.0) or 0.0)
                month_co2 += val
            s1_trend[m - 1] = month_co2
            s1_total += month_co2
    except Exception as e: 
        print("Lỗi Scope 1:", e)

    # ─── 2. SCOPE 2 (Tính từ kWh * EF) ───
    s2_trend = [0.0] * 12
    s2_total = 0.0
    try:
        s2_items = electrical_items_service.get_scope2_categories(db)
        
        GRID_EF = 0.0006235
        
        for item in s2_items:
            kwh = float(item.get("kwh", 0.0) if isinstance(item, dict) else getattr(item, "kwh", 0.0))
            
            if kwh <= 0:
                continue

            raw_date = item.get("entry_date", None) if isinstance(item, dict) else getattr(item, "entry_date", None)
            dt = parse_date(raw_date)
            # Luôn khớp năm với bộ lọc; chế độ "Năm" trước đây bỏ qua năm nên KPI S2 sai và không đổi khi đổi year
            if not (dt and dt.year == current_year):
                continue
            if mf is not None and dt.month not in mf:
                continue

            val_co2 = kwh * GRID_EF
            s2_total += val_co2
            s2_trend[dt.month - 1] += val_co2

    except Exception as e: 
        print("Lỗi Scope 2:", e)


    # ─── 3. SCOPE 3 ───
    s3_trend = [0.0] * 12
    s3_total = 0.0
    c_co2 = 0.0
    s_co2 = 0.0
    total_trips = 0
    containers, ships = [], []

    def _s3_included(obj, is_dict: bool):
        dt = parse_date(obj.get("start_time") if is_dict else getattr(obj, "start_time", None))
        if mf is None:
            return True
        return bool(dt and dt.year == current_year and dt.month in mf)

    try:
        containers = container_service.get_all_containers(db)
        ships = ship_service.get_all_ships(db)

        for c in containers:
            val = float(get_val(c, 'total_co2') or get_val(c, 'e_total'))
            dt = parse_date(c.get('start_time') if isinstance(c, dict) else getattr(c, 'start_time', None))
            if not (dt and dt.year == current_year):
                continue
            if mf is not None and dt.month not in mf:
                continue
            c_co2 += val
            s3_trend[dt.month - 1] += val

        for s in ships:
            val = float(get_val(s, 'total_co2'))
            dt = parse_date(s.get('start_time') if isinstance(s, dict) else getattr(s, 'start_time', None))
            if not (dt and dt.year == current_year):
                continue
            if mf is not None and dt.month not in mf:
                continue
            s_co2 += val
            s3_trend[dt.month - 1] += val

        s3_total = c_co2 + s_co2
        if mf is None:
            total_trips = len(ships) + len(containers)
        else:
            total_trips = sum(1 for c in containers if _s3_included(c, isinstance(c, dict)))
            total_trips += sum(1 for s in ships if _s3_included(s, isinstance(s, dict)))
    except Exception as e:
        print("Lỗi Scope 3:", e)

    containers_shap = [c for c in containers if _s3_included(c, isinstance(c, dict))]
    ships_shap = [s for s in ships if _s3_included(s, isinstance(s, dict))]

    # ─── 4. SHAP & AI INSIGHT ───
    shap_data = calculate_shap_from_data(containers_shap, ships_shap)
    
    if shap_data:
        top = shap_data[0]
        if top['val'] > 0:
            ai_insight = f"Phân tích dữ liệu chỉ ra: <strong>{top['feature_name']}</strong> đang là nguyên nhân lớn nhất làm TĂNG phát thải Scope 3. Việc chỉ số này tăng cao khiến phát thải <strong>tăng trung bình {abs(top['val']):.2f} tấn CO₂e</strong> trên mỗi chuyến. Cần tìm cách hạn chế chỉ số này."
        else:
            ai_insight = f"Phân tích dữ liệu chỉ ra: <strong>{top['feature_name']}</strong> là yếu tố giúp GIẢM phát thải tốt nhất. Việc chỉ số này tăng cao giúp <strong>giảm trung bình {abs(top['val']):.2f} tấn CO₂e</strong>. Đề xuất ưu tiên điều phối các chuyến hàng có đặc điểm này."
    else:
        ai_insight = "Cần thêm các bản ghi có dữ liệu đa dạng (các tàu/xe có công suất, vận tốc khác nhau...) để hệ thống AI có thể phân tích xu hướng."

    # ─── 5. BIỂU ĐỒ TRÒN: CHỈ CƠ CẤU THEO SCOPE 1 / 2 / 3 (không tách thiết bị con) ───
    equip_list = []
    if s1_total > 0:
        equip_list.append({"label": "Scope 1", "value": s1_total})
    if s2_total > 0:
        equip_list.append({"label": "Scope 2", "value": s2_total})
    if s3_total > 0:
        equip_list.append({"label": "Scope 3", "value": s3_total})

    top_labels = [x["label"] for x in equip_list] or ["Chưa có dữ liệu"]
    top_values = [x["value"] for x in equip_list] or [1]

    # Chia quý
    def to_quarters(t): return [sum(t[0:3]), sum(t[3:6]), sum(t[6:9]), sum(t[9:12]), sum(t)]

    data = {
        "total_emissions": s1_total + s2_total + s3_total,
        "scope1_total": s1_total, "scope2_total": s2_total, "scope3_total": s3_total,
        "total_trips": total_trips, "current_year": current_year,
        "period_label": period_label,
        "last_updated": now.strftime("%d/%m/%Y %H:%M"),
        "trend": {"months": ['T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12'], "scope1": s1_trend, "scope2": s2_trend, "scope3": s3_trend},
        "quarterly": {"labels": ["Quý 1", "Quý 2", "Quý 3", "Quý 4", "Cả Năm (YTD)"], "scope1": to_quarters(s1_trend), "scope2": to_quarters(s2_trend), "scope3": to_quarters(s3_trend)},
        "top_equipment": {"labels": top_labels, "values": top_values},
        "shap_data": shap_data,
        "ai_insight": ai_insight
    }

    return templates.TemplateResponse("dashboard/dashboard.html", {"request": request, "user": current_user, "data": data})