# schemas/ship.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from models.ship import ShipType, ValveType

class ShipBase(BaseModel):
    name: str = Field(..., description="Tên tàu")
    ship_type: ShipType = Field(..., description="Loại tàu")
    year_built: int = Field(..., description="Năm đóng tàu")
    buoy: Optional[int] = Field(0, description="Phao số (Buoy) - luôn là 0, không cần nhập")
    deadweight_tonnage: float = Field(..., description="Trọng tải toàn phần (DWT)")
    time_in_port: Optional[float] = Field(None, description="Thời gian lưu cảng (giờ)")
    v_trip: float = Field(..., description="Tốc độ hành trình (V_trip)")
    v_maneuver: float = Field(..., description="Tốc độ điều động (V_maneuver)")
    v_max: float = Field(..., description="Tốc độ tối đa (V_max)")
    P_main: float = Field(..., description="Công suất máy chính (kW)")
    P_aux: Optional[float] = Field(None, description="Công suất máy phụ (kW) - luôn bằng P_main, không cần nhập")
    rpm: float = Field(..., description="Vòng tua máy (RPM)")
    valve_type: ValveType = Field(..., description="Loại van (C3 hoặc SV)")
    is_man: bool = Field(..., description="Có phải là động cơ man hay không?")
    start_time: datetime = Field(..., description="Thời gian vào cảng")
    end_time: datetime = Field(..., description="Thời gian rời cảng")

class ShipCreate(ShipBase):
    def model_post_init(self, __context):
        # Always enforce buoy=0 and P_aux=P_main
        self.buoy = 0
        if self.P_main is not None:
            self.P_aux = 1/5*self.P_main

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


class VoyagePortCall(BaseModel):
    port_code: str = Field(..., description="Mã cảng")
    port_name: Optional[str] = Field(None, description="Tên cảng")
    eta: datetime = Field(..., description="Thời gian tàu đến cảng")
    etd: datetime = Field(..., description="Thời gian tàu rời cảng")
    channel_distance_km: Optional[float] = Field(
        None,
        ge=0,
        description="Chiều dài luồng (km) để tính trip/maneuver trong cảng",
    )
    sea_distance_to_next_km: Optional[float] = Field(
        None,
        ge=0,
        description="Quãng đường biển từ cảng này đến cảng kế tiếp (km)",
    )
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Vĩ độ cảng")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Kinh độ cảng")


class ShipVoyageRequest(BaseModel):
    name: str = Field(..., description="Tên tàu")
    ship_type: ShipType = Field(..., description="Loại tàu")
    year_built: int = Field(..., description="Năm đóng tàu")
    rpm: float = Field(..., gt=0, description="Vòng tua máy")
    valve_type: ValveType = Field(..., description="Loại van")
    is_man: bool = Field(..., description="Động cơ chính là MAN hay không")
    buoy: int = Field(0, ge=0, description="Mã phao fallback khi không truyền channel_distance_km")

    v_trip: float = Field(..., gt=0, description="Tốc độ hành trình trong luồng (km/h)")
    v_maneuver: float = Field(..., gt=0, description="Tốc độ điều động trong cảng (km/h)")
    v_max: float = Field(..., gt=0, description="Tốc độ tối đa của tàu (km/h)")
    v_sea: Optional[float] = Field(None, gt=0, description="Tốc độ thiết kế khi đi biển (km/h)")

    P_main: float = Field(..., gt=0, description="Công suất máy chính (kW)")
    P_aux: Optional[float] = Field(None, gt=0, description="Công suất máy phụ (kW)")
    lf_aux_at_sea: float = Field(0.729, ge=0, le=1, description="Load factor máy phụ khi đi biển")

    sea_buffer_hours: float = Field(
        2.0,
        ge=0,
        description="Khoảng đệm giờ từ ETD trước khi tính quãng đi biển",
    )
    default_sea_speed_ratio: float = Field(
        0.9,
        gt=0,
        le=1.2,
        description="Tỷ lệ tốc độ biển mặc định so với v_max",
    )
    cap_speed_by_design: bool = Field(
        True,
        description="Giới hạn tốc độ đi biển theo v_sea hoặc default_sea_speed_ratio * v_max",
    )

    ports: list[VoyagePortCall] = Field(
        ...,
        min_length=2,
        description="Danh sách cảng theo thứ tự hành trình",
    )

    @model_validator(mode="after")
    def apply_defaults_and_validate(self):
        if self.P_aux is None:
            self.P_aux = self.P_main / 5.0

        for i, port in enumerate(self.ports, start=1):
            if port.etd < port.eta:
                raise ValueError(f"Port call {i} has etd earlier than eta")
        return self