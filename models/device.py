import enum
from sqlalchemy import Column, Integer, Float, String, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship
from core.database import Base

# --- ENUMS ---
class DeviceTypeEnum(str, enum.Enum):
    MOBILE_CRANE = "Mobile Harbor Crane"
    REACH_STACKER = "Reach Stacker"
    YARD_TRACTOR = "Yard Tractor"
    EMPTY_HANDLER = "Empty Container Handler"
    FORKLIFT = "Forklift"
    RTG_CRANE = "RTG crane"

class FuelTypeEnum(str, enum.Enum):
    DIESEL = "Diesel"
    ELECTRIC = "Electric"

class RecordStatusEnum(str, enum.Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    LOCKED = "Locked"

# --- TABLES ---
class DeviceCategory(Base):
    __tablename__ = "scope1_device_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    device_type = Column(Enum(DeviceTypeEnum), nullable=False)          
    fuel_type = Column(Enum(FuelTypeEnum), nullable=False)
    total_quantity = Column(Integer, default=1)                         
    nominal_capacity = Column(Float, nullable=False)                    
    
    activities = relationship("ActivityData", back_populates="category", cascade="all, delete-orphan")


class ActivityData(Base):
    __tablename__ = "scope1_activities"

    id = Column(Integer, primary_key=True, index=True)
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey("scope1_device_categories.id"), nullable=False)
    
    quantity = Column(Integer, default=1, nullable=False)           
    recorded_power = Column(Float, nullable=False)                  
    operating_hours = Column(Float, nullable=False)                 
    load_factor = Column(Float, nullable=False)                     
    total_co2e = Column(Float, nullable=False)                      
    
    status = Column(Enum(RecordStatusEnum), default=RecordStatusEnum.DRAFT, nullable=False)
    category = relationship("DeviceCategory", back_populates="activities")

    __table_args__ = (
        Index('ix_period_status', 'period_year', 'period_month', 'status'),
    )