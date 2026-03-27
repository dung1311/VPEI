# services/device.py
import io
import pandas as pd

from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, UploadFile
from models.scope1 import DeviceCategory, ActivityData, RecordStatusEnum
from schemas.scope1_emission_source import ActivityDataUpdate, DeviceCategoryCreate, ActivityDataCreate, DeviceCategoryUpdate

class DeviceCategoryService:
    @staticmethod
    def get_all(db: Session):
        return db.query(DeviceCategory).all()

    @staticmethod
    def create(db: Session, data: DeviceCategoryCreate):
        existing = db.query(DeviceCategory).filter(DeviceCategory.name == data.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Tên nhóm thiết bị đã tồn tại!")
            
        new_category = DeviceCategory(**data.model_dump())
        db.add(new_category)
        db.commit()
        db.refresh(new_category)
        return new_category
    
    @staticmethod
    def update(db: Session, category_id: int, data: DeviceCategoryUpdate):
        category = db.query(DeviceCategory).filter(DeviceCategory.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhóm thiết bị")
        
        if data.name and data.name != category.name:
            existing = db.query(DeviceCategory).filter(DeviceCategory.name == data.name).first()
            if existing:
                raise HTTPException(status_code=400, detail="Tên nhóm thiết bị đã tồn tại!")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(category, key, value)
            
        db.commit()
        db.refresh(category)
        return category
    
    @staticmethod
    def delete(db: Session, category_id: int):
        category = db.query(DeviceCategory).filter(DeviceCategory.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhóm thiết bị để xóa")
        
        db.delete(category)
        db.commit()
        return {"message": f"Đã xóa thành công nhóm '{category.name}' và các dữ liệu liên quan"}

class ActivityDataService:
    @staticmethod
    def check_period_lock(db: Session, year: int, month: int):
        locked_exists = db.query(ActivityData).filter(
            ActivityData.period_year == year,
            ActivityData.period_month == month,
            ActivityData.status == RecordStatusEnum.LOCKED
        ).first()
        if locked_exists:
            raise HTTPException(status_code=403, detail="Kỳ báo cáo này đã bị Khóa (Locked). Không thể thao tác.")

    @staticmethod
    def create(db: Session, data: ActivityDataCreate):
        ActivityDataService.check_period_lock(db, data.period_year, data.period_month)

        category = db.query(DeviceCategory).filter(DeviceCategory.id == data.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhóm thiết bị")
        
        calculated_co2e = (
            data.recorded_power * data.operating_hours * data.load_factor * category.emission_factor * data.quantity
        )

        new_record = ActivityData(
            period_year=data.period_year,
            period_month=data.period_month,
            category_id=data.category_id,
            quantity=data.quantity,
            recorded_power=data.recorded_power,
            operating_hours=data.operating_hours,
            load_factor=data.load_factor,
            total_co2e=calculated_co2e,
            status=RecordStatusEnum.DRAFT   
        )

        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        return new_record

    @staticmethod
    def update(db: Session, activity_id: int, data: ActivityDataUpdate):
        activity = db.query(ActivityData).filter(ActivityData.id == activity_id).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi hoạt động")
        
        ActivityDataService.check_period_lock(db, activity.period_year, activity.period_month)
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(activity, key, value)
       
        activity.total_co2e = (
            activity.recorded_power * activity.operating_hours * activity.load_factor * activity.category.emission_factor * activity.quantity
        )
        
        db.commit()
        db.refresh(activity)
        return activity

    @staticmethod
    def delete(db: Session, activity_id: int):
        activity = db.query(ActivityData).filter(ActivityData.id == activity_id).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi")
        
        ActivityDataService.check_period_lock(db, activity.period_year, activity.period_month)
        
        db.delete(activity)
        db.commit()
        return {"status": "success", "message": "Đã xóa bản ghi hoạt động"}

    @staticmethod
    async def import_from_excel(db: Session, file: UploadFile, year: int, month: int):
        ActivityDataService.check_period_lock(db, year, month)

        try:
            contents = await file.read()
            df = pd.read_excel(io.BytesIO(contents))
            df.columns = [c.strip() for c in df.columns]
            
            imported_count = 0
            skipped_devices = []

            for index, row in df.iterrows():
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
                    skipped_devices.append(cat_name)
                    continue 
                
                calc_co2 = (power * hours * lf * category.emission_factor * qty)

                new_act = ActivityData(
                    period_year=year,
                    period_month=month,
                    category_id=category.id,
                    quantity=qty,
                    recorded_power=power,
                    operating_hours=hours,
                    load_factor=lf,
                    total_co2e=calc_co2,
                    status=RecordStatusEnum.DRAFT
                )
                db.add(new_act)
                imported_count += 1
            
            if imported_count == 0:
                missing = ", ".join(set(skipped_devices))
                raise HTTPException(status_code=400, detail=f"Không có dòng nào được Import! Không khớp loại thiết bị: {missing}")

            db.commit()
            return {"status": "success", "message": f"Đã import thành công {imported_count} dòng"}
            
        except Exception as e:
            db.rollback()
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=400, detail=f"Lỗi hệ thống: {str(e)}")
        
    @staticmethod
    def get_by_period(db: Session, year: int, month: int):
        return db.query(ActivityData).filter(
            ActivityData.period_year == year,
            ActivityData.period_month == month
        ).all()

    @staticmethod
    def update_period_status(db: Session, year: int, month: int, new_status: RecordStatusEnum):
        activities = db.query(ActivityData).filter(
            ActivityData.period_year == year,
            ActivityData.period_month == month
        ).all()

        if not activities:
            raise HTTPException(status_code=404, detail="Không có dữ liệu trong kỳ này để cập nhật")

        current_statuses = [a.status for a in activities]
        if RecordStatusEnum.LOCKED in current_statuses and new_status != RecordStatusEnum.LOCKED:
             raise HTTPException(status_code=403, detail="Không thể mở khóa dữ liệu đã Locked.")

        for act in activities:
            act.status = new_status
        
        db.commit()
        return {"message": f"Đã chuyển {len(activities)} bản ghi sang {new_status}", "updated": len(activities)}

class DashboardService:
    @staticmethod
    def get_period_summary(db: Session, year: int, month: int):
        activities = db.query(ActivityData).filter(
            ActivityData.period_year == year,
            ActivityData.period_month == month
        ).all()

        if not activities:
            return {
                "total_co2e": 0.0,
                "status": RecordStatusEnum.DRAFT,
                "record_count": 0,
                "is_editable": True
            }

        total = sum(a.total_co2e for a in activities)
        current_statuses = [a.status for a in activities]

        if RecordStatusEnum.LOCKED in current_statuses:
            status = RecordStatusEnum.LOCKED
            is_editable = False
        elif RecordStatusEnum.SUBMITTED in current_statuses:
            status = RecordStatusEnum.SUBMITTED
            is_editable = False
        else:
            status = RecordStatusEnum.DRAFT
            is_editable = True

        return {
            "total_co2e": total,
            "status": status,
            "record_count": len(activities),
            "is_editable": is_editable
        }