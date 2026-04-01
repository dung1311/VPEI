from sqlalchemy import Column, DateTime, Float, Integer, String

from core.database import Base
from models.user import vn_now


class Scope3OtherVehicle(Base):
    __tablename__ = "scope3_other_vehicles"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_type = Column(String, nullable=False, index=True)  # container-ship | barge | tugboat
    name = Column(String, nullable=False)
    period = Column(String, nullable=False)
    trips = Column(Integer, nullable=False, default=0)
    consumption = Column(Float, nullable=False, default=0.0)
    emission_factor = Column(Float, nullable=False)
    e_total = Column(Float, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=vn_now)
