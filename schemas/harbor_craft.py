from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from models.harbor_craft import HarborCraftTypeEnum, EngineTypeEnum

class HarborCraftCreate(BaseModel):
    device_name: str = Field(..., description="Tên thiết bị / Tàu")
    craft_type: HarborCraftTypeEnum = Field(..., description="Loại tàu cảng")
    engine_type: EngineTypeEnum = Field(EngineTypeEnum.MAIN, description="Loại động cơ")
    year_built: int = Field(..., description="Năm đóng tàu")
    power: float = Field(..., description="Công suất (kW)")
    activity_hours: float = Field(..., description="Giờ hoạt động")
    use_rd99: bool = Field(False, description="Sử dụng nhiên liệu tái tạo RD99?")
    engine_tier: str = Field("0-3", description="Cấp động cơ: '0-3' hoặc '4'")
    record_time: datetime

class HarborCraftUpdate(BaseModel):
    device_name: Optional[str] = None
    craft_type: Optional[HarborCraftTypeEnum] = None
    engine_type: Optional[EngineTypeEnum] = None
    year_built: Optional[int] = None
    power: Optional[float] = None
    activity_hours: Optional[float] = None
    use_rd99: Optional[bool] = None
    engine_tier: Optional[str] = None
    record_time: Optional[datetime] = None
    reason: Optional[str] = Field(None, description="Lý do cập nhật")