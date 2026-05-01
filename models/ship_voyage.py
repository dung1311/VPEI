# models/ship_voyage.py
from core.database import Base
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Text, Boolean
from models.ship import ShipType, ValveType


class ShipVoyage(Base):
    __tablename__ = "ship_voyages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ship_type = Column(Enum(ShipType), nullable=False)
    year_built = Column(Integer, nullable=False)
    rpm = Column(Float, nullable=False)
    valve_type = Column(Enum(ValveType), nullable=False)
    is_man = Column(Boolean, nullable=False, default=False)
    buoy = Column(Integer, nullable=True, default=0)

    P_main = Column(Float, nullable=False)
    P_aux = Column(Float, nullable=True)

    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

    total_co2 = Column(Float, nullable=True, default=0.0)
    payload_json = Column(Text, nullable=True)
