from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from models.other_vehicle import OtherVehicleTypeEnum


class OtherVehicleCreate(BaseModel):
    vehicle_type: OtherVehicleTypeEnum = Field(..., description="Loại xe")
    vehicle_count: int = Field(..., ge=1, description="Số lượng xe")
    record_time: datetime


class OtherVehicleUpdate(BaseModel):
    vehicle_type: Optional[OtherVehicleTypeEnum] = None
    vehicle_count: Optional[int] = Field(None, ge=1)
    record_time: Optional[datetime] = None
    reason: Optional[str] = Field(None, description="Lý do cập nhật")
