# services/device.py
import io
import pandas as pd

from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, UploadFile
from models.device import DeviceCategory, ActivityData, RecordStatusEnum
from schemas.device import ActivityDataUpdate, DeviceCategoryCreate, ActivityDataCreate, DeviceCategoryUpdate

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
        # 1. Tìm nhóm thiết bị
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
    def create(db: Session, data: ActivityDataCreate):
        category = db.query(DeviceCategory).filter(DeviceCategory.id == data.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhóm thiết bị")
        
        # CÔNG THỨC: Công suất * Giờ * LoadFactor * Hệ số phát thải * Số lượng xe
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
        
        db.delete(activity)
        db.commit()
        return {"status": "success", "message": "Đã xóa bản ghi hoạt động"}
    @staticmethod
    async def import_from_excel(db: Session, file: UploadFile, year: int, month: int):
        try:
            contents = await file.read()
            df = pd.read_excel(io.BytesIO(contents))
            df.columns = [c.strip() for c in df.columns] # Dọn dẹp khoảng trắng ở tên cột
            
            imported_count = 0
            skipped_devices = []

            for index, row in df.iterrows():
                try:
                    cat_name = str(row['Loại thiết bị']).strip()
                    print(f"Processing row {index}: Device Type='{cat_name}'")  # Debug log
                    qty = int(row['Số lượng'])
                    power = float(row['Power (kW)'])
                    hours = float(row['Giờ hoạt động'])
                    lf = float(row['LF (%)'])
                except KeyError as e:
                    raise HTTPException(status_code=400, detail=f"File Excel thiếu cột: {str(e)}")

                # Tìm nhóm thiết bị
                category = db.query(DeviceCategory).filter(DeviceCategory.device_type == cat_name).first()
                if not category:
                    skipped_devices.append(cat_name) # Lưu lại tên bị sai để báo lỗi
                    continue 
                
                # Tính toán CO2
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
            
            # NẾU KHÔNG CÓ DÒNG NÀO ĐƯỢC IMPORT, BÁO LỖI ĐỂ FRONTEND HIỂN THỊ
            if imported_count == 0:
                missing = ", ".join(set(skipped_devices))
                raise HTTPException(status_code=400, detail=f"Không có dòng nào được Import! Các tên thiết bị trong Excel không khớp với web: {missing}")

            db.commit()
            return {"status": "success", "message": f"Đã import thành công {imported_count} dòng"}
            
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Lỗi hệ thống: {str(e)}")
        
class DashboardService:
    @staticmethod
    def get_summary(db: Session, year: int, month: int):
        total = db.query(func.sum(ActivityData.total_co2e)).filter(
            ActivityData.period_year == year,
            ActivityData.period_month == month
        ).scalar()
        return {"total_co2e": total or 0.0}