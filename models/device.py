# models/device.py
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Enum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from core.database import Base

class DeviceTypeEnum(enum.Enum):
    MOBILE_HARBOR_CRANE = "Mobile Harbor Crane"
    RTG_CRANE = "RTG Crane"
    STS_CRANE = "STS Crane"
    REACH_STACKER = "Reach Stacker"
    FORKLIFT = "Forklift"
    TERMINAL_TRACTOR = "Terminal Tractor"
    OTHER = "Khác"

class FuelTypeEnum(enum.Enum):
    DIESEL = "Diesel"
    GASOLINE = "Gasoline"
    LNG = "LNG"
    ELECTRICITY = "Electricity"
    OTHER = "Khác"

class Device(Base):
    """
    Quản lý danh sách các thiết bị/phương tiện vật lý cụ thể.
    """
    __tablename__ = "devices"

    id = Column(String, primary_key=True, index=True) # ID dạng String do người dùng nhập
    name = Column(String, index=True, nullable=False) # Ví dụ: "Xe nâng RTG-01"
    device_type = Column(Enum(DeviceTypeEnum), nullable=False)
    
    # Đặt mặc định nhiên liệu là DIESEL
    fuel_type = Column(Enum(FuelTypeEnum), default=FuelTypeEnum.DIESEL, nullable=False)
    nominal_capacity = Column(Float, nullable=False) 
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Quan hệ 1-N: 1 Thiết bị có thể có nhiều bản ghi hoạt động
    activities = relationship("ActivityData", back_populates="device", cascade="all, delete")

class ActivityData(Base):
    """
    Lưu trữ lịch sử hoạt động chi tiết (thời gian làm việc, mức tiêu thụ, phát thải)
    """
    __tablename__ = "activity_data"

    id = Column(Integer, primary_key=True, index=True)
    
    # [FIXED] Sửa thành String để trỏ đúng Khóa ngoại tới devices.id
    device_id = Column(String, ForeignKey("devices.id"), nullable=False)
    
    # Lưu trực tiếp loại thiết bị để tiện group by và hiển thị trên UI không cần JOIN
    device_type = Column(Enum(DeviceTypeEnum), nullable=False)

    recorded_power = Column(Float, nullable=False)
    operating_hours = Column(Float, nullable=False)
    load_factor = Column(Float, nullable=False)
    total_co2e = Column(Float, nullable=False)
    
    record_time = Column(DateTime, default=datetime.now, nullable=False) 
    
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    device = relationship("Device", back_populates="activities")