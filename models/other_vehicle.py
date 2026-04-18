import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, Integer

from core.database import Base


class OtherVehicleTypeEnum(enum.Enum):
    CAR = "car"
    MOTORBIKE = "motorbike"


class OtherVehicle(Base):
    __tablename__ = "s3_other_vehicles"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_type = Column(Enum(OtherVehicleTypeEnum), nullable=False)
    vehicle_count = Column(Integer, nullable=False, default=1)
    emission_factor = Column(Float, nullable=False)
    distance_km = Column(Float, nullable=False, default=1.0)
    e_total = Column(Float, nullable=False)
    record_time = Column(DateTime, default=datetime.now, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
