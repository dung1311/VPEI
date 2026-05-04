# models/ship.py
import enum
from enum import Enum

try:
    from enum import StrEnum
except ImportError:
    # Python < 3.11
    class StrEnum(str, Enum):
        pass

from core.database import Base
from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, Float, Integer, String

class ShipType(StrEnum):
    CONTAINER = "container_ship"
    BULK = "bulk_carrier"
    CRUISER = "cruiser_ship"
    GENERAL = "general_cargo_ship"
    OTHER = "other_ship"
    RORO = "roro_ship"
    REEFER = "reefer_ship"
    OIL_TANKER = "oil_tanker"

class ValveType(StrEnum):
    C3 = "C3"
    SV = "SV"

class Ship(Base):
    __tablename__ = "ships"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ship_type = Column(SQLEnum(ShipType), nullable=False)
    year_built = Column(Integer, nullable=False)
    buoy = Column(Integer, nullable=False)
    deadweight_tonnage = Column(Float, nullable=False)
    time_in_port = Column(Float, nullable=False)
    v_trip = Column(Float, nullable=False)
    v_maneuver = Column(Float, nullable=False)
    v_max = Column(Float, nullable=False)
    P_main = Column(Float, nullable=False)
    P_aux = Column(Float, nullable=False)
    rpm = Column(Float, nullable=False)
    valve_type = Column(SQLEnum(ValveType), nullable=False)
    is_man = Column(Boolean, nullable=False, default=0)  
    start_time = Column(DateTime, nullable=True) 
    end_time = Column(DateTime, nullable=True)
    total_co2 = Column(Float, nullable=True, default=0.0)





