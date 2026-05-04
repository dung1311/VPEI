from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from models.harbor_craft import HarborCraftTypeEnum, EngineTypeEnum

class HarborCraftCreate(BaseModel):
    device_name: str = Field(..., description="Tên thiết bị / Tàu")
    craft_type: HarborCraftTypeEnum = Field(..., description="Loại tàu cảng")
    engine_type: EngineTypeEnum = Field(EngineTypeEnum.MAIN, description="Loại động cơ")
    year_built: int = Field(..., ge=1900, le=2100, description="Năm đóng tàu")
    power: float = Field(..., gt=0, description="Công suất (kW)")
    activity_hours: float = Field(..., ge=0, description="Giờ hoạt động")
    use_rd99: bool = Field(False, description="Sử dụng nhiên liệu tái tạo RD99?")
    engine_tier: str = Field("0-3", pattern=r"^(0-3|4)$", description="Cấp động cơ: '0-3' hoặc '4'")
    record_time: datetime

class HarborCraftUpdate(BaseModel):
    device_name: Optional[str] = None
    craft_type: Optional[HarborCraftTypeEnum] = None
    engine_type: Optional[EngineTypeEnum] = None
    year_built: Optional[int] = Field(None, ge=1900, le=2100)
    power: Optional[float] = Field(None, gt=0)
    activity_hours: Optional[float] = Field(None, ge=0)
    use_rd99: Optional[bool] = None
    engine_tier: Optional[str] = Field(None, pattern=r"^(0-3|4)$")
    record_time: Optional[datetime] = None
    reason: Optional[str] = Field(None, description="Lý do cập nhật")