# services/scope1.py
import io
from typing import List, Set
import pandas as pd
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.device import DeviceCategory, ActivityData, RecordStatusEnum
from core.constants import STATIC_EF

from schemas.device import (
    DeviceCategoryCreate,
    DeviceCategoryUpdate,
    ActivityDataCreate,
    ActivityDataUpdate,
)

class DeviceCategoryService:
    @staticmethod
    def get_all(db: Session) -> List[DeviceCategory]:
        cats = db.query(DeviceCategory).all()
        for c in cats:
            c.emission_factor = STATIC_EF.get(c.device_type.value, STATIC_EF["Default"])
        return cats

    @staticmethod
    def get(db: Session, category_id: int):
        c = db.query(DeviceCategory).filter(DeviceCategory.id == category_id).first()
        if c:
            c.emission_factor = STATIC_EF.get(c.device_type.value, STATIC_EF["Default"])
        return c

    @staticmethod
    def create(db: Session, payload: DeviceCategoryCreate):
        existing = db.query(DeviceCategory).filter(DeviceCategory.name == payload.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Tên nhóm thiết bị đã tồn tại")

        new = DeviceCategory(**payload.model_dump())
        db.add(new)
        db.commit()
        db.refresh(new)
        new.emission_factor = STATIC_EF.get(new.device_type.value, STATIC_EF["Default"])
        return new

    @staticmethod
    def update(db: Session, category_id: int, payload: DeviceCategoryUpdate):
        category = db.query(DeviceCategory).filter(DeviceCategory.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhóm thiết bị")

        if payload.name and payload.name != category.name:
            exist = db.query(DeviceCategory).filter(DeviceCategory.name == payload.name).first()
            if exist:
                raise HTTPException(status_code=400, detail="Tên nhóm thiết bị đã tồn tại")

        update_data = payload.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(category, k, v)

        db.commit()
        db.refresh(category)
        category.emission_factor = STATIC_EF.get(category.device_type.value, STATIC_EF["Default"])
        return category

    @staticmethod
    def delete(db: Session, category_id: int):
        category = db.query(DeviceCategory).filter(DeviceCategory.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhóm thiết bị để xóa")
        db.delete(category)
        db.commit()
        return {"message": "Đã xóa nhóm thiết bị"}


class ActivityDataService:
    @staticmethod
    def check_period_lock(db: Session, year: int, month: int):
        locked = db.query(ActivityData).filter(
            ActivityData.period_year == year,
            ActivityData.period_month == month,
            ActivityData.status == RecordStatusEnum.LOCKED,
        ).first()
        if locked:
            raise HTTPException(status_code=403, detail="Kỳ báo cáo này đã bị Khóa (Locked). Không thể thao tác.")

    @staticmethod
    def create(db: Session, payload: ActivityDataCreate):
        ActivityDataService.check_period_lock(db, payload.period_year, payload.period_month)

        category = db.query(DeviceCategory).filter(DeviceCategory.id == payload.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhóm thiết bị")

        lf = payload.load_factor or 0.0
        if lf > 1: lf = lf / 100.0

        ef = STATIC_EF.get(category.device_type.value, STATIC_EF["Default"])
        total_co2e = (payload.recorded_power * payload.operating_hours * lf * ef * payload.quantity) / 1000.0

        rec = ActivityData(
            period_year=payload.period_year,
            period_month=payload.period_month,
            category_id=payload.category_id,
            quantity=payload.quantity,
            recorded_power=payload.recorded_power,
            operating_hours=payload.operating_hours,
            load_factor=lf,
            total_co2e=total_co2e,
            status=RecordStatusEnum.DRAFT,
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

        ActivityDataService.check_period_lock(db, act.period_year, act.period_month)

        update_data = payload.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(act, k, v)

        lf = act.load_factor if act.load_factor is not None else 0.0
        if lf > 1: lf = lf / 100.0

        ef = STATIC_EF.get(act.category.device_type.value, STATIC_EF["Default"])

        act.load_factor = lf
        act.total_co2e = (act.recorded_power * act.operating_hours * lf * ef * act.quantity) / 1000.0

        db.commit()
        db.refresh(act)
        return act

    @staticmethod
    def delete(db: Session, activity_id: int):
        act = db.query(ActivityData).filter(ActivityData.id == activity_id).first()
        if not act:
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi")

        ActivityDataService.check_period_lock(db, act.period_year, act.period_month)

        db.delete(act)
        db.commit()
        return {"message": "Đã xóa bản ghi hoạt động"}

    @staticmethod
    def get_by_period(db: Session, year: int, month: int):
        return db.query(ActivityData).filter(
            ActivityData.period_year == year,
            ActivityData.period_month == month,
        ).all()

    @staticmethod
    async def import_from_excel(db: Session, file: UploadFile, year: int, month: int):
        ActivityDataService.check_period_lock(db, year, month)

        try:
            contents = await file.read()
            df = pd.read_excel(io.BytesIO(contents))
            df.columns = [c.strip() for c in df.columns]

            imported = 0
            skipped = []

            for _, row in df.iterrows():
                try:
                    cat_name = str(row['Loại thiết bị']).strip()
                    qty = int(row['Số lượng'])
                    power = float(row['Power (kW)'])
                    hours = float(row['Giờ hoạt động'])
                    lf = float(row['LF (%)'])
                except KeyError as e:
                    raise HTTPException(status_code=400, detail=f"File Excel thiếu cột: {str(e)}")

                category = db.query(DeviceCategory).filter(DeviceCategory.device_type == cat_name).first()
                if not category:
                    skipped.append(cat_name)
                    continue

                if lf > 1: lf = lf / 100.0

                ef = STATIC_EF.get(category.device_type.value, STATIC_EF["Default"])
                calc = (power * hours * lf * ef * qty) / 1000.0

                new_act = ActivityData(
                    period_year=year,
                    period_month=month,
                    category_id=category.id,
                    quantity=qty,
                    recorded_power=power,
                    operating_hours=hours,
                    load_factor=lf,
                    total_co2e=calc,
                    status=RecordStatusEnum.DRAFT,
                )
                db.add(new_act)
                imported += 1

            if imported == 0:
                missing = ", ".join(set(skipped))
                raise HTTPException(status_code=400, detail=f"Không có dòng nào được Import! Không khớp loại thiết bị: {missing}")

            db.commit()
            return {"status": "success", "imported": imported}

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Lỗi khi import Excel: {str(e)}")

    @staticmethod
    def update_period_status(db: Session, year: int, month: int, new_status: RecordStatusEnum):
        acts = db.query(ActivityData).filter(
            ActivityData.period_year == year,
            ActivityData.period_month == month,
        ).all()

        if not acts:
            raise HTTPException(status_code=404, detail="Không có dữ liệu trong kỳ này để cập nhật")

        current = [a.status for a in acts]
        if RecordStatusEnum.LOCKED in current and new_status != RecordStatusEnum.LOCKED:
            raise HTTPException(status_code=403, detail="Không thể mở khóa dữ liệu đã Locked.")

        for a in acts:
            a.status = new_status

        db.commit()
        return {"updated": len(acts), "new_status": new_status}


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

        acts = db.query(ActivityData.status).filter(
            ActivityData.period_year == year,
            ActivityData.period_month.in_(months_sorted),
        ).all()

        period_status = RecordStatusEnum.DRAFT
        if acts:
            statuses = [a[0] for a in acts]
            if RecordStatusEnum.LOCKED in statuses:
                period_status = RecordStatusEnum.LOCKED
            elif RecordStatusEnum.SUBMITTED in statuses:
                period_status = RecordStatusEnum.SUBMITTED

        cur = db.query(
            func.sum(ActivityData.total_co2e).label('total_co2e'),
            func.sum(ActivityData.recorded_power * ActivityData.operating_hours * ActivityData.load_factor).label('total_energy')
        ).filter(
            ActivityData.period_year == year,
            ActivityData.period_month.in_(months_sorted),
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
                ActivityData.period_year == prev_year,
                ActivityData.period_month == prev_month,
            ).scalar() or 0.0
            if prev_co2e > 0:
                mom = ((total_co2e - prev_co2e) / prev_co2e) * 100.0
            elif total_co2e > 0 and prev_co2e == 0:
                mom = 100.0

        top = db.query(
            DeviceCategory.name,
            func.sum(ActivityData.total_co2e).label('co2e')
        ).join(DeviceCategory).filter(
            ActivityData.period_year == year,
            ActivityData.period_month.in_(months_sorted),
        ).group_by(DeviceCategory.name).order_by(func.sum(ActivityData.total_co2e).desc()).first()

        top_name = top.name if top else "N/A"
        top_co2e = top.co2e if top else 0.0

        bar_rows = db.query(
            DeviceCategory.device_type,
            func.sum(ActivityData.total_co2e).label('co2e')
        ).join(DeviceCategory).filter(
            ActivityData.period_year == year,
            ActivityData.period_month.in_(months_sorted),
        ).group_by(DeviceCategory.device_type).order_by(func.sum(ActivityData.total_co2e).desc()).limit(8).all()

        bar_chart = {"labels": [r[0].value for r in bar_rows], "values": [r[1] for r in bar_rows]}

        line_labels = [f"T{i}" for i in range(1, 13)]
        line_values = []
        for m in range(1, 13):
            if m in months_set:
                val = db.query(func.sum(ActivityData.total_co2e)).filter(
                    ActivityData.period_year == year,
                    ActivityData.period_month == m,
                ).scalar() or 0.0
            else:
                val = 0.0
            line_values.append(val)

        table_data = []
        if total_co2e > 0:
            rows = db.query(
                DeviceCategory.device_type,
                DeviceCategory.fuel_type,
                func.sum(ActivityData.recorded_power * ActivityData.operating_hours * ActivityData.load_factor).label('energy'),
                func.sum(ActivityData.total_co2e).label('co2e')
            ).join(DeviceCategory).filter(
                ActivityData.period_year == year,
                ActivityData.period_month.in_(months_sorted),
            ).group_by(DeviceCategory.device_type, DeviceCategory.fuel_type).all()

            for r in rows:
                table_data.append({
                    "device_name": r[0].value,
                    "fuel_type": r[1].value,
                    "consumption": (r[2] or 0.0) * 0.25,
                    "total_co2e": r[3] or 0.0,
                    "percentage": ((r[3] or 0.0) / total_co2e) * 100.0,
                })

        return {
            "kpis": {
                "total_fuel": total_fuel,
                "total_co2e": total_co2e,
                "top_emitter_name": top_name,
                "top_emitter_co2e": top_co2e,
                "mom_growth": mom,
                "status": period_status.value
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
                'device_name': 'Loại Thiết Bị',
                'fuel_type': 'Nhiên Liệu',
                'consumption': 'Tiêu Thụ (L)',
                'total_co2e': 'Phát Thải (tCO2e)',
                'percentage': 'Tỷ Trọng (%)',
            })

        tag = "_".join(str(m) for m in sorted(set(months)))[:60]
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name=f"S1_{year}_{tag}"[:31], index=False)
        output.seek(0)
        return output