from docxtpl import DocxTemplate
from docx import Document
from docx.shared import RGBColor, Pt
import io
import os
import math
from calendar import monthrange
from datetime import date, datetime, time
from typing import Optional, Set, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import extract, or_, and_

# [UPDATED] Import Device thay cho DeviceCategory
from models.device import ActivityData, Device 
from models.electrical_item import ElectricalItem
from models.ship import Ship
from models.container import Container
from models.scope3_other_vehicle import Scope3OtherVehicle
from services.ship_service import calculate_ship_co2

def _report_months(month: Optional[int], quarter: Optional[int]) -> Optional[Set[int]]:
    if month is not None:
        return {month}
    if quarter is not None:
        q = int(quarter)
        return set(range((q - 1) * 3 + 1, q * 3 + 1))
    return None

def _parse_period_value_date(raw: Optional[str]) -> Optional[date]:
    s = (raw or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def _year_month_pairs_in_range(d_start: date, d_end: date) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    cur = date(d_start.year, d_start.month, 1)
    while cur <= d_end:
        last = date(cur.year, cur.month, monthrange(cur.year, cur.month)[1])
        if last >= d_start and cur <= d_end:
            out.append((cur.year, cur.month))
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return out


class ReportService:
    @staticmethod
    def set_cell(cell, text):
        cell.text = "" 
        run = cell.paragraphs[0].add_run(str(text))
        run.font.name = 'Times New Roman'
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(0, 0, 0)
        run.bold = True
        run.font.highlight_color = None

    @staticmethod
    def generate_vpei_final_report(
        db: Session,
        year: int,
        month: Optional[int] = None,
        quarter: Optional[int] = None,
        date_start: Optional[date] = None,
        date_end: Optional[date] = None,
        include_appendix: bool = True,
    ) -> bytes:
        use_range = date_start is not None and date_end is not None
        if use_range:
            if date_start > date_end:
                raise ValueError("date_start phải trước hoặc bằng date_end")
            start_time_s = date_start.strftime("%d/%m/%Y")
            end_time_s = date_end.strftime("%d/%m/%Y")
            mf = None
        else:
            mf = _report_months(month, quarter)
            if month is not None:
                d1 = monthrange(year, month)[1]
                start_time_s = f"01/{month:02d}/{year}"
                end_time_s = f"{d1:02d}/{month:02d}/{year}"
            elif quarter is not None:
                qn = int(quarter)
                sm, em = (qn - 1) * 3 + 1, qn * 3
                d1 = monthrange(year, em)[1]
                start_time_s = f"01/{sm:02d}/{year}"
                end_time_s = f"{d1:02d}/{em:02d}/{year}"
            else:
                start_time_s = f"01/01/{year}"
                end_time_s = f"31/12/{year}"

        # ==========================================
        # 1. Fetch Real Data from Database
        # ==========================================

        # --- Scope 1: ActivityData ---
        # [UPDATED] JOIN với Device thay vì DeviceCategory
        if use_range:
            pairs = _year_month_pairs_in_range(date_start, date_end)
            if pairs:
                q_s1 = db.query(ActivityData).join(Device).filter(
                    or_(*[and_(ActivityData.period_year == py, ActivityData.period_month == pm) for py, pm in pairs])
                )
            else:
                q_s1 = db.query(ActivityData).join(Device).filter(ActivityData.id == -1)
            scope1_activities = q_s1.all()
        else:
            q_s1 = db.query(ActivityData).join(Device).filter(ActivityData.period_year == year)
            if mf is not None:
                q_s1 = q_s1.filter(ActivityData.period_month.in_(mf))
            scope1_activities = q_s1.order_by(ActivityData.record_time.desc()).all()

        s1_co2e = sum(act.total_co2e for act in scope1_activities) if scope1_activities else 0.0
        s1_co2 = s1_co2e
        s1_ch4 = 0.0
        s1_n2o = 0.0

        data_scope1 = []
        for idx, act in enumerate(scope1_activities, 1):
            # [UPDATED] Lấy tên từ bảng Device
            device_name = act.device.name if act.device else "Unknown Device"
            operating_hours = act.operating_hours
            power = act.recorded_power
            co2 = round(act.total_co2e, 2)
            
            # Thay vì "N/A", hiển thị Thời gian ghi nhận để báo cáo chi tiết hơn
            record_time_str = act.record_time.strftime("%d/%m/%Y") if getattr(act, 'record_time', None) else "N/A"
            
            data_scope1.append([idx, device_name, record_time_str, power, operating_hours, co2])

        # --- Scope 2: Electricity ---
        all_elec = db.query(ElectricalItem).all()
        if use_range:
            scope2_items = []
            for e in all_elec:
                dv = _parse_period_value_date(e.period_value)
                if dv is not None and date_start <= dv <= date_end:
                    scope2_items.append(e)
        else:
            scope2_items = [e for e in all_elec if e.period_value and str(year) in e.period_value]

        s2_co2e = 0.0
        data_scope2 = []
        for idx, item in enumerate(scope2_items, 1):
            e_total = (item.power * 720 * 0.8 * 0.6235 / 1000) if item.power else 0.0
            if item.period_type == 'year':
                e_total *= 12

            s2_co2e += e_total
            data_scope2.append([idx, item.name, item.period_value, f"{item.power} kW", round(e_total, 2)])

        s2_co2 = s2_co2e
        s2_ch4 = 0.0
        s2_n2o = 0.0

        # --- Scope 3: Ships, Containers, Other Vehicles ---
        if use_range:
            t0 = datetime.combine(date_start, time.min)
            t1 = datetime.combine(date_end, time.max)
            q_sh = db.query(Ship).filter(Ship.start_time.isnot(None), Ship.start_time >= t0, Ship.start_time <= t1)
            q_ct = db.query(Container).filter(Container.start_time.isnot(None), Container.start_time >= t0, Container.start_time <= t1)
            ships = q_sh.all()
            containers = q_ct.all()
            all_ov = db.query(Scope3OtherVehicle).all()

            def _ov_in_range(v: Scope3OtherVehicle) -> bool:
                d = _parse_period_value_date(v.period)
                if d is not None:
                    return date_start <= d <= date_end
                p = v.period or ""
                for yy in range(date_start.year, date_end.year + 1):
                    if str(yy) in p:
                        return True
                return False

            other_vehicles = [v for v in all_ov if _ov_in_range(v)]
        else:
            q_sh = db.query(Ship).filter(extract("year", Ship.start_time) == year)
            q_ct = db.query(Container).filter(extract("year", Container.start_time) == year)
            if mf is not None:
                mlist = list(mf)
                q_sh = q_sh.filter(extract("month", Ship.start_time).in_(mlist))
                q_ct = q_ct.filter(extract("month", Container.start_time).in_(mlist))
            ships = q_sh.all()
            containers = q_ct.all()
            other_vehicles = db.query(Scope3OtherVehicle).all()
            other_vehicles = [v for v in other_vehicles if v.period and str(year) in v.period]

        s3_co2e_ships = 0.0
        data_tau_bien = []
        data_tau_cang = []
        for idx, ship in enumerate(ships, 1):
            co2 = calculate_ship_co2(ship)
            s3_co2e_ships += co2
            
            start_str = ship.start_time.strftime("%d/%m %H:%M") if ship.start_time else ""
            end_str = ship.end_time.strftime("%d/%m %H:%M") if ship.end_time else ""
            
            if "lai dắt" in ship.name.lower() or "hoa tiêu" in ship.name.lower() or ship.ship_type == "Tàu cảng":
                data_tau_cang.append([len(data_tau_cang)+1, ship.name, ship.year_built, ship.P_main, ship.P_aux, round(co2, 2)])
            else:
                data_tau_bien.append([len(data_tau_bien)+1, ship.name, start_str, end_str, ship.deadweight_tonnage, ship.P_main, round(co2, 2)])

        s3_co2e_containers = 0.0
        data_xe_cont = []
        for idx, con in enumerate(containers, 1):
            co2 = con.e_total if con.e_total else 0.0
            s3_co2e_containers += co2
            
            start_str = con.start_time.strftime("%d/%m %H:%M") if con.start_time else ""
            end_str = con.end_time.strftime("%d/%m %H:%M") if con.end_time else ""
            data_xe_cont.append([idx, con.license_plate, start_str, end_str, con.journey_type, round(co2, 2)])

        s3_co2e_other = 0.0
        xe_may_count = 0
        xe_may_co2 = 0.0
        oto_count = 0
        oto_co2 = 0.0
        
        for v in other_vehicles:
            co2 = v.e_total if v.e_total else 0.0
            s3_co2e_other += co2
            if "máy" in v.vehicle_type.lower():
                xe_may_count += v.trips if v.trips else 1
                xe_may_co2 += co2
            else:
                oto_count += v.trips if v.trips else 1
                oto_co2 += co2

        s3_co2e = s3_co2e_ships + s3_co2e_containers + s3_co2e_other
        s3_co2 = s3_co2e
        s3_ch4 = 0.0
        s3_n2o = 0.0

        sum_co2e = s1_co2e + s2_co2e + s3_co2e
        
        if sum_co2e == 0:
            sum_co2e = 1.0

        s1_w = f"{round((s1_co2e / sum_co2e) * 100, 2)}%"
        s2_w = f"{round((s2_co2e / sum_co2e) * 100, 2)}%"
        s3_w = f"{round((s3_co2e / sum_co2e) * 100, 2)}%"

        context = {
            'company_name': 'Công ty TNHH Cảng Nam Đình Vũ',
            'start_time': start_time_s,
            'end_time': end_time_s,
            'seaport_name': 'Nam Đình Vũ - Hải Phòng',
            's1_co2': round(s1_co2, 2), 's1_ch4': round(s1_ch4, 2), 's1_n2o': round(s1_n2o, 2), 's1_co2e': round(s1_co2e, 2), 's1_w': s1_w,
            's2_co2': round(s2_co2, 2), 's2_ch4': round(s2_ch4, 2), 's2_n2o': round(s2_n2o, 2), 's2_co2e': round(s2_co2e, 2), 's2_w': s2_w,
            's3_co2': round(s3_co2, 2), 's3_ch4': round(s3_ch4, 2), 's3_n2o': round(s3_n2o, 2), 's3_co2e': round(s3_co2e, 2), 's3_w': s3_w,
            'sum_co2e': round(sum_co2e, 2) if sum_co2e != 1.0 else 0.0
        }

        template_path = "./static/VPEI_report_apd.docx" if include_appendix else "./static/VPEI_report.docx"
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template {template_path} not found")

        doc = DocxTemplate(template_path)
        doc.render(context)
        
        temp_io = io.BytesIO()
        doc.save(temp_io)
        temp_io.seek(0)

        # ==========================================
        # 2. FILL TABLES USING PYTHON-DOCX
        # ==========================================
        final_doc = Document(temp_io)

        try:
            for item in data_scope1:
                cells = final_doc.tables[2].add_row().cells
                for idx, val in enumerate(item): ReportService.set_cell(cells[idx], val)

            for item in data_scope2:
                cells = final_doc.tables[3].add_row().cells
                for idx, val in enumerate(item): ReportService.set_cell(cells[idx], val)

            for item in data_tau_bien:
                cells = final_doc.tables[4].add_row().cells
                for idx, val in enumerate(item): ReportService.set_cell(cells[idx], val)

            for item in data_xe_cont:
                cells = final_doc.tables[5].add_row().cells
                for idx, val in enumerate(item): ReportService.set_cell(cells[idx], val)

            for item in data_tau_cang:
                cells = final_doc.tables[6].add_row().cells
                for idx, val in enumerate(item): ReportService.set_cell(cells[idx], val)

            if len(final_doc.tables) > 7:
                table_phuong_tien = final_doc.tables[7]
                ReportService.set_cell(table_phuong_tien.rows[1].cells[1], xe_may_count)
                ReportService.set_cell(table_phuong_tien.rows[1].cells[3], round(xe_may_co2, 2))
                ReportService.set_cell(table_phuong_tien.rows[2].cells[1], oto_count)
                ReportService.set_cell(table_phuong_tien.rows[2].cells[3], round(oto_co2, 2))

        except IndexError as e:
            print(f"Lỗi cấu trúc bảng: {e}")

        final_output_io = io.BytesIO()
        final_doc.save(final_output_io)
        final_output_io.seek(0)
        return final_output_io.read()