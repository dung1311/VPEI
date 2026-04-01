from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime
from models.device import DeviceTypeEnum, FuelTypeEnum, RecordStatusEnum

class DeviceCategoryBase(BaseModel):
    name: str
    device_type: DeviceTypeEnum
    fuel_type: FuelTypeEnum
    total_quantity: int = 1
    nominal_capacity: float

class DeviceCategoryCreate(DeviceCategoryBase):
    pass

class DeviceCategoryUpdate(BaseModel):
    name: Optional[str] = None
    device_type: Optional[DeviceTypeEnum] = None
    fuel_type: Optional[FuelTypeEnum] = None
    total_quantity: Optional[int] = None
    nominal_capacity: Optional[float] = None

class DeviceCategoryResponse(DeviceCategoryBase):
    id: int
    created_at: datetime
    emission_factor: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class ActivityDataBase(BaseModel):
    period_year: int
    period_month: int
    category_id: int
    quantity: int = Field(..., gt=0)
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

class PeriodStatusUpdate(BaseModel):
    year: int
    month: int
    new_status: RecordStatusEnum

class DashboardKPIs(BaseModel):
    total_fuel: float
    total_co2e: float
    top_emitter_name: str
    top_emitter_co2e: float
    mom_growth: float
    status: str

class ChartData(BaseModel):
    labels: List[str]
    values: List[float]

class DashboardResponse(BaseModel):
    kpis: DashboardKPIs
    bar_chart: ChartData
    line_chart: ChartData
    table_data: List[Dict]