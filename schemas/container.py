from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from models.container import JourneyType


class ContainerCreate(BaseModel):
    license_plate: str
    start_time: datetime
    end_time: datetime
    max_weight: float = 40.0
    journey_type: JourneyType
    velocity_1: float
    velocity_2: float
    velocity_3: float
    input_weight: float
    output_weight: float
    distance_1: float
    distance_2: float
    distance_3: float


class ContainerUpdate(BaseModel):
    license_plate: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    max_weight: Optional[float] = None
    journey_type: Optional[JourneyType] = None
    velocity_1: Optional[float] = None
    velocity_2: Optional[float] = None
    velocity_3: Optional[float] = None
    input_weight: Optional[float] = None
    output_weight: Optional[float] = None
    distance_1: Optional[float] = None
    distance_2: Optional[float] = None
    distance_3: Optional[float] = None
    reason: Optional[str] = None  # Reason for update


class ContainerResponse(BaseModel):
    id: int
    license_plate: Optional[str]
    start_time: datetime
    end_time: datetime
    duration: float
    max_weight: float
    journey_type: JourneyType
    container_weight_type: str
    velocity: float
    velocity_1: float
    velocity_2: float
    velocity_3: float
    input_weight: float
    output_weight: float
    distance_1: float
    distance_2: float
    distance_3: float
    e_total: float

    class Config:
        from_attributes = True
