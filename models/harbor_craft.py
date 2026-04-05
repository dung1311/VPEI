import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum
from core.database import Base

class HarborCraftTypeEnum(enum.Enum):
    ATB = "atb"
    ASSIST_TUG = "assist_tug"
    BARGE = "barge"
    COMMERCIAL_FISHING = "commercial_fishing"
    CREW_BOAT = "crew_boat"
    EXCURSION = "excursion"
    FERRY = "ferry"
    GOVERNMENT = "government"
    OCEAN_TUG = "ocean_tug"
    TUGBOAT = "tugboat"
    WORK_BOAT = "work_boat"
    OTHER = "other"

class EngineTypeEnum(enum.Enum):
    MAIN = "main"
    AUX = "aux"

class HarborCraft(Base):
    __tablename__ = "s3_harbor_crafts"

    id = Column(Integer, primary_key=True, index=True)
    
    # --- BIẾN ĐỘC LẬP ---
    device_name = Column(String, index=True, nullable=False)
    
    # Bắt buộc sử dụng ENUM
    craft_type = Column(Enum(HarborCraftTypeEnum), nullable=False, default=HarborCraftTypeEnum.OTHER)
    engine_type = Column(Enum(EngineTypeEnum), nullable=False, default=EngineTypeEnum.MAIN)
    
    year_built = Column(Integer, nullable=False)
    power = Column(Float, nullable=False)
    activity_hours = Column(Float, nullable=False)
    use_rd99 = Column(Boolean, default=False) 
    engine_tier = Column(String, default="0-3")
    
    # --- BIẾN PHỤ THUỘC ---
    lf = Column(Float, nullable=False)
    zh = Column(Float, default=762.0, nullable=False) 
    dr = Column(Float, default=0.0, nullable=False)   
    fcf = Column(Float, default=1.0, nullable=False)  
    cf = Column(Float, default=1.0, nullable=False)   
    
    cumulative_hours = Column(Float, nullable=False)
    ef_final = Column(Float, nullable=False)
    e_total = Column(Float, nullable=False) 
    
    record_time = Column(DateTime, default=datetime.now, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)