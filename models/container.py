import enum

from core.database import Base
from sqlalchemy import Boolean, Column, DateTime, Enum, Float, Integer, String


class JourneyType(str, enum.Enum):
    BOTH = "both"          # Nhập và xuất
    EXPORT_ONLY = "export" # Chỉ xuất
    IMPORT_ONLY = "import" # Chỉ nhập


class ContainerWeightType(str, enum.Enum):
    TYPE_1 = "type_1"
    TYPE_2 = "type_2"


class Container(Base):
    __tablename__ = "containers"

    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String, nullable=False)

    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration = Column(Float, nullable=True)
    max_weight = Column(Float, nullable=False, default=40.0)

    journey_type = Column(Enum(JourneyType), nullable=False)
    container_weight_type = Column(Enum(ContainerWeightType), nullable=False)
    is_refrigerated = Column(Boolean, nullable=False, default=False)
    velocity = Column(Float, nullable=True)
    velocity_1 = Column(Float, nullable=False)
    velocity_2 = Column(Float, nullable=False)
    velocity_3 = Column(Float, nullable=False)

    input_weight = Column(Float, nullable=False)
    output_weight = Column(Float, nullable=False)

    payload_1 = Column(Float, nullable=False)
    payload_2 = Column(Float, nullable=False)
    payload_3 = Column(Float, nullable=False)

    ef1 = Column(Float, nullable=False)
    ef2 = Column(Float, nullable=False)
    ef3 = Column(Float, nullable=False)

    distance_1 = Column(Float, nullable=False)
    distance_2 = Column(Float, nullable=False)
    distance_3 = Column(Float, nullable=False)

    time1 = Column(Float, nullable=False)
    time2 = Column(Float, nullable=False)
    time3 = Column(Float, nullable=False)

    waited_time = Column(Float, nullable=False)
    active_waited_time = Column(Float, nullable=False)

    e_total = Column(Float, nullable=False)