import enum
from core.database import Base
from sqlalchemy import Column, Integer, String,  Float, Enum

class ItemLocation(str, enum.Enum):
    MAIN_PORT = "Cảng chính"
    WAREHOUSE = "Kho bãi"
    OFFICE = "Văn phòng"
    CONTAINER_YARD = "Bãi container"
    CHECKPOINT = "Trạm kiểm soát"

class ElectricalItem(Base):
    __tablename__ = "electrical_items"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String, index=True, nullable=False)
    power        = Column(Float, nullable=False)  # Power consumption in kilo watts
    location     = Column(Enum(ItemLocation), nullable=True)  # Optional location of the item
    description  = Column(String, nullable=True)
    period_type  = Column(String, nullable=True, default="month") # "day", "month", "quarter", "year"
    period_value = Column(String, nullable=True, default="") # e.g. "Tháng 06 - 2026"
