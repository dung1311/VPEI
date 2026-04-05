# services/scope1.py
import io
import random
from typing import List, Set
import pandas as pd
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime
from calendar import monthrange

from models.device import Device, ActivityData, DeviceTypeEnum, FuelTypeEnum
from core.constants import STATIC_EF
from schemas.device import DeviceCreate, DeviceUpdate, ActivityDataCreate, ActivityDataUpdate

class DeviceService:
    @staticmethod
    def get_all(db: Session) -> List[Device]:
        devices = db.query(Device).all()
        for d in devices:
            d.emission_factor = STATIC_EF.get(d.device_type.value, STATIC_EF.get("Default", 1.0))
        return devices

    @staticmethod
    def get(db: Session, device_id: str):
        d = db.query(Device).filter(Device.id == device_id).first()
        if d:
            d.emission_factor = STATIC_EF.get(d.device_type.value, STATIC_EF.get("Default", 1.0))
        return d

    @staticmethod
    def create(db: Session, payload: DeviceCreate):
        existing = db.query(Device).filter(Device.id == payload.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Mã ID thiết bị đã tồn tại trong hệ thống")

        new_device = Device(**payload.model_dump())
        db.add(new_device)
        db.commit()
        db.refresh(new_device)
        new_device.emission_factor = STATIC_EF.get(new_device.device_type.value, STATIC_EF.get("Default", 1.0))
        return new_device

    @staticmethod
    def update(db: Session, device_id: str, payload: DeviceUpdate):
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")

        update_data = payload.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(device, k, v)

        db.commit()
        db.refresh(device)
        device.emission_factor = STATIC_EF.get(device.device_type.value, STATIC_EF.get("Default", 1.0))
        return device

    @staticmethod
    def delete(db: Session, device_id: str):
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị để xóa")
        db.delete(device)
        db.commit()
        return {"message": "Đã xóa thiết bị"}


class ActivityDataService:
    @staticmethod
    def create(db: Session, payload: ActivityDataCreate):
        device = db.query(Device).filter(Device.id == payload.device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")

        lf = payload.load_factor or 0.0
        if lf > 1: lf = lf / 100.0

        ef = STATIC_EF.get(device.device_type.value, STATIC_EF.get("Default", 1.0))
        total_co2e = (payload.recorded_power * payload.operating_hours * lf * ef) / 1000.0

        rec = ActivityData(
            device_id=payload.device_id,
            device_type=device.device_type,
            recorded_power=payload.recorded_power,
            operating_hours=payload.operating_hours,
            load_factor=lf,
            total_co2e=total_co2e,
            record_time=payload.record_time,
            period_month=payload.record_time.month,
            period_year=payload.record_time.year,
        )

        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def update(db: Session, activity_id: int, payload: ActivityDataUpdate):
        act = db.query(ActivityData).filter(ActivityData.id == activity_id).first()
        if not act:
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi hoạt động")

        update_data = payload.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(act, k, v)

        if payload.device_id:
            device = db.query(Device).filter(Device.id == payload.device_id).first()
            if device:
                act.device_type = device.device_type
        
        lf = act.load_factor if act.load_factor is not None else 0.0
        if lf > 1: lf = lf / 100.0

        ef = STATIC_EF.get(act.device_type.value, STATIC_EF.get("Default", 1.0))
        act.load_factor = lf
        act.total_co2e = (act.recorded_power * act.operating_hours * lf * ef) / 1000.0
        
        if payload.record_time:
            act.period_month = payload.record_time.month
            act.period_year = payload.record_time.year

        db.commit()
        db.refresh(act)
        return act

    @staticmethod
    def delete(db: Session, activity_id: int):
        act = db.query(ActivityData).filter(ActivityData.id == activity_id).first()
        if not act:
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi")
        db.delete(act)
        db.commit()
        return {"message": "Đã xóa bản ghi hoạt động"}

    @staticmethod
    def get_by_record_time(db: Session, year: int, months: List[int]):
        return db.query(ActivityData).filter(
            extract('year', ActivityData.record_time) == year,
            extract('month', ActivityData.record_time).in_(months)
        ).order_by(ActivityData.record_time.desc()).all()

    @staticmethod
    async def import_from_excel(db: Session, file: UploadFile, year: int, month: int):
        try:
            contents = await file.read()
            df = pd.read_excel(io.BytesIO(contents))
            df.columns = [c.strip() for c in df.columns]

            imported = 0
            
            for _, row in df.iterrows():
                try:
                    dev_id = str(row['Mã thiết bị (ID)']).strip()
                    power = float(row['Power (kW)'])
                    hours = float(row['Giờ hoạt động'])
                    lf = float(row['LF (%)'])
                    
                    raw_time = row.get('Thời gian (YYYY-MM-DD HH:MM)', None)
                    if pd.isna(raw_time) or raw_time == "":
                        record_time = datetime(year, month, 1, 8, 0)
                    else:
                        record_time = pd.to_datetime(raw_time)
                except KeyError as e:
                    raise HTTPException(status_code=400, detail=f"File Excel thiếu cột: {str(e)}")

                device = db.query(Device).filter(Device.id == dev_id).first()
                
                # TỰ ĐỘNG TẠO THIẾT BỊ NẾU CHƯA CÓ TRONG DB ĐỂ TEST DỄ DÀNG
                if not device:
                    dev_type_str = str(row.get('Loại thiết bị', 'Khác')).strip()
                    try:
                        dt_enum = DeviceTypeEnum(dev_type_str)
                    except ValueError:
                        dt_enum = DeviceTypeEnum.OTHER
                        
                    device = Device(
                        id=dev_id,
                        name=f"Thiết bị {dev_id}",
                        device_type=dt_enum,
                        fuel_type=FuelTypeEnum.DIESEL,
                        nominal_capacity=power
                    )
                    db.add(device)
                    db.commit()
                    db.refresh(device)

                if lf > 1: lf = lf / 100.0
                ef = STATIC_EF.get(device.device_type.value, STATIC_EF.get("Default", 1.0))
                calc = (power * hours * lf * ef) / 1000.0

                new_act = ActivityData(
                    period_year=record_time.year,
                    period_month=record_time.month,
                    device_id=device.id,
                    device_type=device.device_type,
                    recorded_power=power,
                    operating_hours=hours,
                    load_factor=lf,
                    total_co2e=calc,
                    record_time=record_time
                )
                db.add(new_act)
                imported += 1

            db.commit()
            return {"status": "success", "imported": imported}

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Lỗi khi import Excel: {str(e)}")

    @staticmethod
    def generate_excel_template(db: Session, year: int, month: int):
        data = []
        _, max_days = monthrange(year, month)
        device_types = [e.value for e in DeviceTypeEnum]
        
        # Random 40 dòng test đa dạng
        for i in range(1, 41):
            dev_id = f"DEMO-{i:02d}"
            dev_type = random.choice(device_types)
            power = round(random.uniform(1200.0, 5000.0), 1)
            hours = round(random.uniform(90, 240.0), 1)
            lf = round(random.uniform(40.0, 95.0), 1)
            
            day = random.randint(1, max_days)
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            record_time = f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"
            
            data.append({
                "Mã thiết bị (ID)": dev_id,
                "Loại thiết bị": dev_type,
                "Power (kW)": power,
                "Giờ hoạt động": hours,
                "LF (%)": lf,
                "Thời gian (YYYY-MM-DD HH:MM)": record_time
            })
            
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Import_Template")
            worksheet = writer.sheets['Import_Template']
            for i, col in enumerate(df.columns):
                column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, column_len)
                
        output.seek(0)
        return output


class DashboardService:
    @staticmethod
    def get_dashboard_data(db: Session, year: int, month: int):
        return DashboardService.get_dashboard_data_for_months(db, year, [month])

    @staticmethod
    def get_dashboard_data_for_months(db: Session, year: int, months: List[int]):
        months_set: Set[int] = set(int(m) for m in months if m)
        months_sorted = sorted(months_set)
        if not months_sorted:
            months_sorted = list(range(1, 13))
            months_set = set(months_sorted)

        cur = db.query(
            func.sum(ActivityData.total_co2e).label('total_co2e'),
            func.sum(ActivityData.recorded_power * ActivityData.operating_hours * ActivityData.load_factor).label('total_energy')
        ).filter(
            extract('year', ActivityData.record_time) == year,
            extract('month', ActivityData.record_time).in_(months_sorted),
        ).first()

        total_co2e = cur.total_co2e or 0.0
        total_energy = cur.total_energy or 0.0
        total_fuel = total_energy * 0.25

        mom = 0.0
        if len(months_sorted) == 1:
            month = months_sorted[0]
            prev_year = year if month > 1 else year - 1
            prev_month = month - 1 if month > 1 else 12
            prev_co2e = db.query(func.sum(ActivityData.total_co2e)).filter(
                extract('year', ActivityData.record_time) == prev_year,
                extract('month', ActivityData.record_time) == prev_month,
            ).scalar() or 0.0
            
            if prev_co2e > 0:
                mom = ((total_co2e - prev_co2e) / prev_co2e) * 100.0
            elif total_co2e > 0 and prev_co2e == 0:
                mom = 100.0

        top = db.query(
            Device.name,
            func.sum(ActivityData.total_co2e).label('co2e')
        ).join(Device, ActivityData.device_id == Device.id).filter(
            extract('year', ActivityData.record_time) == year,
            extract('month', ActivityData.record_time).in_(months_sorted),
        ).group_by(Device.name).order_by(func.sum(ActivityData.total_co2e).desc()).first()

        top_name = top.name if top else "N/A"
        top_co2e = top.co2e if top else 0.0

        bar_rows = db.query(
            ActivityData.device_type,
            func.sum(ActivityData.total_co2e).label('co2e')
        ).filter(
            extract('year', ActivityData.record_time) == year,
            extract('month', ActivityData.record_time).in_(months_sorted),
        ).group_by(ActivityData.device_type).order_by(func.sum(ActivityData.total_co2e).desc()).limit(8).all()

        bar_chart = {"labels": [r[0].value for r in bar_rows], "values": [r[1] for r in bar_rows]}

        line_labels = [f"T{i}" for i in range(1, 13)]
        line_values = []
        for m in range(1, 13):
            if m in months_set:
                val = db.query(func.sum(ActivityData.total_co2e)).filter(
                    extract('year', ActivityData.record_time) == year,
                    extract('month', ActivityData.record_time) == m,
                ).scalar() or 0.0
            else:
                val = 0.0
            line_values.append(val)

        activities = db.query(ActivityData, Device).join(Device, ActivityData.device_id == Device.id).filter(
            extract('year', ActivityData.record_time) == year,
            extract('month', ActivityData.record_time).in_(months_sorted),
        ).order_by(ActivityData.record_time.desc()).all()

        table_data = []
        for act, dev in activities:
            table_data.append({
                "id": act.id,
                "device_id": dev.id,
                "device_name": dev.name,
                "power": act.recorded_power,
                "operating_hours": act.operating_hours,
                "lf": act.load_factor * 100.0,
                "total_co2e": act.total_co2e,
                "record_time": act.record_time.strftime("%d/%m/%Y %H:%M") if act.record_time else ""
            })

        return {
            "kpis": {
                "total_fuel": total_fuel,
                "total_co2e": total_co2e,
                "top_emitter_name": top_name,
                "top_emitter_co2e": top_co2e,
                "mom_growth": mom,
            },
            "bar_chart": bar_chart,
            "line_chart": {"labels": line_labels, "values": line_values},
            "table_data": table_data,
        }

    @staticmethod
    def export_excel(db: Session, year: int, months: List[int]):
        data = DashboardService.get_dashboard_data_for_months(db, year, months)
        df = pd.DataFrame(data['table_data'])
        
        if not df.empty:
            df = df.rename(columns={
                'id': 'ID Bản ghi',
                'device_id': 'Mã Thiết Bị',
                'device_name': 'Tên Thiết Bị',
                'power': 'Công suất (kW)',
                'operating_hours': 'Giờ hoạt động (h)',
                'lf': 'LF (%)',
                'total_co2e': 'Phát Thải (tCO2e)',
                'record_time': 'Thời gian ghi nhận',
            })

        tag = "_".join(str(m) for m in sorted(set(months)))[:60]
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name=f"S1_ChiTiet_{year}_{tag}"[:31], index=False)
        output.seek(0)
        return output