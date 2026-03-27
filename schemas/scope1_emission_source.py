# schemas/device.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from models.scope1 import DeviceTypeEnum, FuelTypeEnum, RecordStatusEnum

# ==========================================
class DeviceCategoryBase(BaseModel):
    name: str
    device_type: DeviceTypeEnum
    fuel_type: FuelTypeEnum
    total_quantity: int
    nominal_capacity: float
    emission_factor: Optional[float] = 0.0765

class DeviceCategoryCreate(DeviceCategoryBase):
    pass

class DeviceCategoryResponse(DeviceCategoryBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
class DeviceCategoryUpdate(BaseModel):
    name: Optional[str] = None
    device_type: Optional[DeviceTypeEnum] = None
    fuel_type: Optional[FuelTypeEnum] = None
    total_quantity: Optional[int] = None      
    nominal_capacity: Optional[float] = None  

# ==========================================
class ActivityDataBase(BaseModel):
    period_year: int
    period_month: int
    category_id: int # Gắn vào ID của nhóm
    quantity: int = Field(..., gt=0) # Số lượng xe nhập liệu
    recorded_power: float
    operating_hours: float
    load_factor: float = Field(..., ge=0.0, le=1.0) 

class ActivityDataCreate(ActivityDataBase):
    pass

class ActivityDataUpdate(BaseModel):
    quantity: Optional[int] = Field(None, gt=0)
    recorded_power: Optional[float] = None
    operating_hours: Optional[float] = None
    load_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    
class ActivityDataResponse(ActivityDataBase):
    id: int
    total_co2e: float
    status: RecordStatusEnum
    created_at: datetime
    
    category: Optional[DeviceCategoryResponse] = None 
    model_config = ConfigDict(from_attributes=True)

class PeriodStatusResponse(BaseModel):
    year: int
    month: int
    status: RecordStatusEnum 
    total_co2e: float
    record_count: int

    # schemas/device.py
from pydantic import BaseModel
from models.scope1 import RecordStatusEnum

class PeriodStatusUpdate(BaseModel):
    year: int
    month: int
    new_status: RecordStatusEnum

class PeriodSummaryResponse(BaseModel):
    year: int
    month: int
    overall_status: RecordStatusEnum
    total_co2e: float
    record_count: int
    is_editable: bool 