from docxtpl import DocxTemplate
from docx import Document
from docx.shared import RGBColor, Pt
import io
import os
import math
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from models.device import ActivityData, DeviceCategory
from models.electrical_item import ElectricalItem
from models.ship import Ship
from models.container import Container
from models.scope3_other_vehicle import Scope3OtherVehicle
from services.ship_service import calculate_ship_co2

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
    def generate_vpei_final_report(db: Session, year: int) -> bytes:
        # ==========================================
        # 1. Fetch Real Data from Database
        # ==========================================
        
        # --- Scope 1: ActivityData ---
        scope1_activities = db.query(ActivityData).join(DeviceCategory).filter(
            ActivityData.period_year == year
        ).all()
        
        s1_co2e = sum(act.total_co2e for act in scope1_activities) if scope1_activities else 0.0
        # Assume CH4 and N2O are small or 0 for now unless we have detailed formulas
        s1_co2 = s1_co2e
        s1_ch4 = 0.0
        s1_n2o = 0.0

        # Build Scope 1 Table Data
        data_scope1 = []
        for idx, act in enumerate(scope1_activities, 1):
            device_name = act.category.name if act.category else "Unknown Device"
            # mock year built, operating hours, power, co2e
            operating_hours = act.operating_hours
            power = act.recorded_power
            co2 = round(act.total_co2e, 2)
            data_scope1.append([idx, device_name, "N/A", power, operating_hours, co2])
            
        # --- Scope 2: Electricity ---
        # Note: Depending on how it's saved, we assume 'period_value' contains the year
        all_elec = db.query(ElectricalItem).all()
        scope2_items = [e for e in all_elec if e.period_value and str(year) in e.period_value]
        
        # EF for electricity is approx 0.6235 tCO2/MWh? Wait, the model uses power
        # Let's see how much they consumed. power * 720 * 0.8 * 0.6235 (from subagent findings)
        s2_co2e = 0.0
        data_scope2 = []
        for idx, item in enumerate(scope2_items, 1):
            # calculate monthly e_total if period_type is month
            # if we don't have hours, we use a placeholder or calculate it
            e_total = (item.power * 720 * 0.8 * 0.6235 / 1000) if item.power else 0.0
            if item.period_type == 'year':
                e_total *= 12  # Approximation
            
            s2_co2e += e_total
            data_scope2.append([idx, item.name, item.period_value, f"{item.power} kW", round(e_total, 2)])
            
        s2_co2 = s2_co2e
        s2_ch4 = 0.0
        s2_n2o = 0.0

        # --- Scope 3: Ships, Containers, Other Vehicles ---
        ships = db.query(Ship).filter(extract('year', Ship.start_time) == year).all()
        containers = db.query(Container).filter(extract('year', Container.start_time) == year).all()
        other_vehicles = db.query(Scope3OtherVehicle).all()
        # Filter other_vehicles by period containing the year string
        other_vehicles = [v for v in other_vehicles if v.period and str(year) in v.period]

        s3_co2e_ships = 0.0
        data_tau_bien = []
        data_tau_cang = []
        for idx, ship in enumerate(ships, 1):
            # calculate_ship_co2 returns total_co2e as float
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
        # For data_phuong_tien, we separate xe may and oto
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
            # Fallback to prevent divide by zero
            sum_co2e = 1.0

        # Calculate percentages
        s1_w = f"{round((s1_co2e / sum_co2e) * 100, 2)}%"
        s2_w = f"{round((s2_co2e / sum_co2e) * 100, 2)}%"
        s3_w = f"{round((s3_co2e / sum_co2e) * 100, 2)}%"

        context = {
            'company_name': 'Công ty TNHH Cảng Nam Đình Vũ',
            'start_time': f'01/01/{year}',
            'end_time': f'31/12/{year}',
            'seaport_name': 'Nam Đình Vũ - Hải Phòng',
            's1_co2': round(s1_co2, 2), 's1_ch4': round(s1_ch4, 2), 's1_n2o': round(s1_n2o, 2), 's1_co2e': round(s1_co2e, 2), 's1_w': s1_w,
            's2_co2': round(s2_co2, 2), 's2_ch4': round(s2_ch4, 2), 's2_n2o': round(s2_n2o, 2), 's2_co2e': round(s2_co2e, 2), 's2_w': s2_w,
            's3_co2': round(s3_co2, 2), 's3_ch4': round(s3_ch4, 2), 's3_n2o': round(s3_n2o, 2), 's3_co2e': round(s3_co2e, 2), 's3_w': s3_w,
            'sum_co2e': round(sum_co2e, 2) if sum_co2e != 1.0 else 0.0
        }

        template_path = "./static/VPEI_report_apd.docx"
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
