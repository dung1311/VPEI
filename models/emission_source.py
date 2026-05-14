import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from core.database import Base


class CalculationMethodEnum(str, enum.Enum):
    METHOD_1 = "method_1"
    METHOD_2 = "method_2"
    METHOD_3 = "method_3"
    METHOD_4 = "method_4"


class ScopeCategory(Base):
    __tablename__ = "scope_categories"

    id = Column(Integer, primary_key=True, index=True)
    scope = Column(Integer, nullable=False, index=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint("scope", "code", name="uq_scope_categories_scope_code"),
    )

    equipments_1 = relationship("Scope1Equipment", back_populates="category")
    equipments_3 = relationship("Scope3Equipment", back_populates="category")


class Scope1Equipment(Base):
    __tablename__ = "scope1_equipments"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("scope_categories.id"), nullable=False, index=True)
    sequence_no = Column(Integer, nullable=False)
    code = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=1)
    unit = Column(String, nullable=False)
    calculation_method = Column(Enum(CalculationMethodEnum), nullable=False)
    emission_factor_json = Column(JSON, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    category = relationship("ScopeCategory", back_populates="equipments_1")
    records = relationship("Scope1EmissionRecord", back_populates="equipment", cascade="all, delete-orphan")


class Scope1EmissionRecord(Base):
    __tablename__ = "scope1_emission_records"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("scope1_equipments.id"), nullable=False, index=True)
    record_time = Column(DateTime, nullable=False, index=True)
    input_json = Column(JSON, nullable=False)
    co2e = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    equipment = relationship("Scope1Equipment", back_populates="records")


class Scope3Equipment(Base):
    __tablename__ = "scope3_equipments"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("scope_categories.id"), nullable=False, index=True)
    sequence_no = Column(Integer, nullable=False)
    code = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=1)
    unit = Column(String, nullable=False)
    calculation_method = Column(Enum(CalculationMethodEnum), nullable=False)
    emission_factor_json = Column(JSON, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    category = relationship("ScopeCategory", back_populates="equipments_3")
    records = relationship("Scope3EmissionRecord", back_populates="equipment", cascade="all, delete-orphan")


class Scope3EmissionRecord(Base):
    __tablename__ = "scope3_emission_records"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("scope3_equipments.id"), nullable=False, index=True)
    record_time = Column(DateTime, nullable=False, index=True)
    input_json = Column(JSON, nullable=False)
    co2e = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    equipment = relationship("Scope3Equipment", back_populates="records")
