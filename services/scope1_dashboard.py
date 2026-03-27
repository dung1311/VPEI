# services/scope1_dashboard.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.scope1 import ActivityData, DeviceCategory
import pandas as pd
import io

class Scope1DashboardService:
    
    @staticmethod
    def get_dashboard_data(db: Session, year: int, month: int):
        # 1. Tính KPIs tháng hiện tại
        current_month_data = db.query(
            func.sum(ActivityData.total_co2e).label('total_co2e'),
            func.sum(ActivityData.recorded_power * ActivityData.operating_hours * ActivityData.load_factor).label('total_energy') # Giả lập nhiên liệu tiêu thụ
        ).filter(
            ActivityData.period_year == year,
            ActivityData.period_month == month
        ).first()

        total_co2e = current_month_data.total_co2e or 0.0
        # Giả sử 1 kWh = 0.25 Lít nhiên liệu (Tùy chỉnh theo hệ số thực tế của bạn)
        total_fuel = (current_month_data.total_energy or 0.0) * 0.25 

        # 2. So sánh với tháng trước (MoM Growth)
        prev_year = year if month > 1 else year - 1
        prev_month = month - 1 if month > 1 else 12
        
        prev_month_co2e = db.query(func.sum(ActivityData.total_co2e)).filter(
            ActivityData.period_year == prev_year,
            ActivityData.period_month == prev_month
        ).scalar() or 0.0

        mom_growth = 0.0
        if prev_month_co2e > 0:
            mom_growth = ((total_co2e - prev_month_co2e) / prev_month_co2e) * 100

        # 3. Top Emitter (Thiết bị phát thải cao nhất tháng này)
        top_emitter = db.query(
            DeviceCategory.name,
            func.sum(ActivityData.total_co2e).label('co2e')
        ).join(DeviceCategory).filter(
            ActivityData.period_year == year,
            ActivityData.period_month == month
        ).group_by(DeviceCategory.name).order_by(func.sum(ActivityData.total_co2e).desc()).first()

        top_emitter_name = top_emitter.name if top_emitter else "N/A"
        top_emitter_co2e = top_emitter.co2e if top_emitter else 0.0

        # 4. Dữ liệu Biểu đồ cột (Bar Chart - Các thiết bị)
        bar_data = db.query(
            DeviceCategory.device_type,
            func.sum(ActivityData.total_co2e).label('co2e')
        ).join(DeviceCategory).filter(
            ActivityData.period_year == year,
            ActivityData.period_month == month
        ).group_by(DeviceCategory.device_type).order_by(func.sum(ActivityData.total_co2e).desc()).limit(8).all()
        
        bar_chart = {"labels": [r[0] for r in bar_data], "values": [r[1] for r in bar_data]}

        # 5. Dữ liệu Biểu đồ đường (Line Chart - 12 tháng gần nhất)
        line_labels = []
        line_values = []
        for i in range(11, -1, -1):
            m = month - i
            y = year
            if m <= 0:
                m += 12
                y -= 1
            
            val = db.query(func.sum(ActivityData.total_co2e)).filter(
                ActivityData.period_year == y,
                ActivityData.period_month == m
            ).scalar() or 0.0
            
            line_labels.append(f"{m}/{y}")
            line_values.append(val)
            
        line_chart = {"labels": line_labels, "values": line_values}

        # 6. Dữ liệu Bảng (Table Data)
        table_data = []
        if total_co2e > 0:
            raw_table = db.query(
                DeviceCategory.device_type,
                DeviceCategory.fuel_type,
                func.sum(ActivityData.recorded_power * ActivityData.operating_hours * ActivityData.load_factor).label('energy'),
                func.sum(ActivityData.total_co2e).label('co2e')
            ).join(DeviceCategory).filter(
                ActivityData.period_year == year,
                ActivityData.period_month == month
            ).group_by(DeviceCategory.device_type, DeviceCategory.fuel_type).all()

            for r in raw_table:
                table_data.append({
                    "device_name": r[0],
                    "fuel_type": r[1],
                    "consumption": (r[2] or 0.0) * 0.25, # Đổi ra Lít giả định
                    "total_co2e": r[3] or 0.0,
                    "percentage": ((r[3] or 0.0) / total_co2e) * 100
                })

        return {
            "kpis": {
                "total_fuel": total_fuel,
                "total_co2e": total_co2e,
                "top_emitter_name": top_emitter_name,
                "top_emitter_co2e": top_emitter_co2e,
                "mom_growth": mom_growth
            },
            "bar_chart": bar_chart,
            "line_chart": line_chart,
            "table_data": table_data
        }

    @staticmethod
    def export_excel(db: Session, year: int, month: int):
        """Xuất dữ liệu Dashboard ra file Excel"""
        data = Scope1DashboardService.get_dashboard_data(db, year, month)
        
        # Tạo DataFrame cho bảng
        df = pd.DataFrame(data["table_data"])
        df.columns = ["Loại Thiết Bị", "Nhiên Liệu", "Tiêu Thụ (L)", "Phát Thải (tCO2e)", "Tỷ Trọng (%)"]
        
        # Ghi ra in-memory file
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name=f'Thang_{month}_{year}', index=False)
        output.seek(0)
        return output