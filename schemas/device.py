# schemas/device.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from models.device import DeviceTypeEnum, FuelTypeEnum

# ==========================================
# SCHEMAS CHO DEVICE
# ==========================================

class DeviceBase(BaseModel):
    id: str = Field(..., description="Mã thiết bị duy nhất (VD: KALMAR-01)")
    name: str = Field(..., description="Tên thiết bị chi tiết")
    device_type: DeviceTypeEnum = Field(..., description="Phân loại thiết bị")
    fuel_type: FuelTypeEnum = Field(default=FuelTypeEnum.DIESEL, description="Loại nhiên liệu")
    nominal_capacity: float = Field(..., description="Công suất định mức thiết kế (kW)")

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    device_type: Optional[DeviceTypeEnum] = None
    fuel_type: Optional[FuelTypeEnum] = None
    nominal_capacity: Optional[float] = None

class DeviceResponse(DeviceBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# SCHEMAS CHO ACTIVITY DATA
# ==========================================

class ActivityDataBase(BaseModel):
    device_id: str = Field(..., description="ID/Mã của thiết bị thực hiện hoạt động")
    recorded_power: float = Field(..., description="Công suất hoạt động thực tế (kW)")
    operating_hours: float = Field(..., description="Thời gian hoạt động (h)")
    load_factor: float = Field(..., description="Hệ số tải LF (%)")
    total_co2e: float = Field(..., description="Tổng phát thải (tCO2e)")
    record_time: datetime = Field(..., description="Thời điểm ghi nhận hoạt động")
    period_month: int = Field(..., description="Tháng báo cáo (1-12)")
    period_year: int = Field(..., description="Năm báo cáo")

class ActivityDataCreate(ActivityDataBase):
    pass

class ActivityDataUpdate(BaseModel):
    device_id: Optional[str] = None
    recorded_power: Optional[float] = None
    operating_hours: Optional[float] = None
    load_factor: Optional[float] = None
    total_co2e: Optional[float] = None
    record_time: Optional[datetime] = None
    period_month: Optional[int] = None
    period_year: Optional[int] = None

class ActivityDataResponse(ActivityDataBase):
    id: int
    device_type: DeviceTypeEnum
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True