# models/device.py
from enum import StrEnum
from sqlalchemy import Column, Index, Integer, String, Float, Enum, ForeignKey, DateTime, Boolean
from core.database import Base
from sqlalchemy.orm import relationship
from models.user import vn_now

class DeviceTypeEnum(StrEnum):
    MOBILE_CRANE = "Mobile Crane"
    REACH_STACKER = "Reach Stacker"         
    TERBERG = "Terberg"
    FORKLIFT = "Forklift"

class FuelTypeEnum(StrEnum):
    DIESEL = "Diesel"
    DO = "Dầu DO"
    FO = "Dầu FO"
    PETROL = "Xăng"
    LNG = "Khí LNG"
    ELECTRICITY = "Điện"

class RecordStatusEnum(StrEnum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    LOCKED = "Locked"

# ==========================================
# BẢNG 1: NHÓM THIẾT BỊ (Đại diện cho 4 Loại xe)
# ==========================================
class DeviceCategory(Base):
    __tablename__ = "device_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True) 
    
    device_type = Column(Enum(DeviceTypeEnum), nullable=False)
    fuel_type = Column(Enum(FuelTypeEnum), nullable=False)
    
    # Thông số kỹ thuật mặc định chung cho cả nhóm
    total_quantity = Column(Integer, default=1, nullable=False) # Tổng số xe trong bãi
    nominal_capacity = Column(Float, nullable=False) # Công suất (kW)
    emission_factor = Column(Float, nullable=False, default=0.000765)      
    
    created_at = Column(DateTime(timezone=True), default=vn_now)

    # 1 Nhóm có nhiều bản ghi dữ liệu hoạt động
    activities = relationship("ActivityData", back_populates="category", cascade="all, delete-orphan")

# ==========================================
# BẢNG 2: DỮ LIỆU HOẠT ĐỘNG (Theo từng đợt nhập tay)
# ==========================================
class ActivityData(Base):
    __tablename__ = "activity_data"

    id = Column(Integer, primary_key=True, index=True)
    period_year = Column(Integer, nullable=False, index=True)
    period_month = Column(Integer, nullable=False, index=True)
    
    # Nối thẳng vào Nhóm thiết bị
    category_id = Column(Integer, ForeignKey("device_categories.id"), nullable=False)
    
    # Thông số đầu vào của 1 lô xe
    quantity = Column(Integer, nullable=False, default=1) # Số lượng xe trong đợt nhập này
    recorded_power = Column(Float, nullable=False)
    operating_hours = Column(Float, nullable=False)
    load_factor = Column(Float, nullable=False)
    
    # Kết quả phát thải
    total_co2e = Column(Float, nullable=False) 
    
    status = Column(Enum(RecordStatusEnum), default=RecordStatusEnum.DRAFT)
    created_at = Column(DateTime(timezone=True), default=vn_now)

    category = relationship("DeviceCategory", back_populates="activities")
    __table_args__ = (Index('ix_period', 'period_year', 'period_month'),)