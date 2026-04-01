# schemas/ship.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from models.ship import ShipType, ValveType

class ShipBase(BaseModel):
    name: str = Field(..., description="Tên tàu")
    ship_type: ShipType = Field(..., description="Loại tàu")
    year_built: int = Field(..., description="Năm đóng tàu")
    buoy: int = Field(..., description="Phao số (Buoy)")
    deadweight_tonnage: float = Field(..., description="Trọng tải toàn phần (DWT)")
    time_in_port: Optional[float] = Field(None, description="Thời gian lưu cảng (giờ)")
    v_trip: float = Field(..., description="Tốc độ hành trình (V_trip)")
    v_maneuver: float = Field(..., description="Tốc độ điều động (V_maneuver)")
    v_max: float = Field(..., description="Tốc độ tối đa (V_max)")
    P_main: float = Field(..., description="Công suất máy chính (kW)")
    P_aux: float = Field(..., description="Công suất máy phụ (kW)")
    rpm: float = Field(..., description="Vòng tua máy (RPM)")
    valve_type: ValveType = Field(..., description="Loại van (C3 hoặc SV)")
    is_man: bool = Field(..., description="Có phải là động cơ man hay không?")
    start_time: datetime = Field(..., description="Thời gian vào cảng")
    end_time: datetime = Field(..., description="Thời gian rời cảng")

class ShipCreate(ShipBase):
    pass

class ShipUpdate(BaseModel):
    name: Optional[str] = None
    ship_type: Optional[ShipType] = None
    year_built: Optional[int] = None
    buoy: Optional[int] = None
    deadweight_tonnage: Optional[float] = None
    time_in_port: Optional[float] = None
    v_trip: Optional[float] = None
    v_maneuver: Optional[float] = None
    v_max: Optional[float] = None
    P_main: Optional[float] = None
    P_aux: Optional[float] = None
    rpm: Optional[float] = None
    valve_type: Optional[ValveType] = None
    is_man: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class ShipResponse(ShipBase):
    id: int
    total_co2: Optional[float] = Field(None, description="Tổng phát thải CO2 (Tấn) được tính toán tự động")
    
    model_config = ConfigDict(from_attributes=True)