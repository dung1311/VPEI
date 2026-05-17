from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from models.emission_source import CalculationMethodEnum


class ScopeCategoryBase(BaseModel):
    scope: int = Field(..., ge=1, le=3)
    code: str = Field(..., min_length=1, max_length=10)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class ScopeCategoryCreate(ScopeCategoryBase):
    pass


class ScopeCategoryUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class ScopeCategoryResponse(ScopeCategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EquipmentBase(BaseModel):
    category_id: int
    name: str = Field(..., min_length=1, max_length=255)
    quantity: float = Field(default=1.0, gt=0)
    unit: str = Field(..., min_length=1, max_length=100)
    calculation_method: CalculationMethodEnum
    emission_factor_json: Optional[dict[str, Any]] = None
    description: Optional[str] = None


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    quantity: Optional[float] = Field(default=None, gt=0)
    unit: Optional[str] = None
    calculation_method: Optional[CalculationMethodEnum] = None
    emission_factor_json: Optional[dict[str, Any]] = None
    description: Optional[str] = None


class EquipmentResponse(EquipmentBase):
    id: int
    scope: int
    sequence_no: int
    code: str
    category_code: str
    category_name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EquipmentRecordBase(BaseModel):
    equipment_id: int
    record_time: datetime


class EquipmentRecordCreate(EquipmentRecordBase):
    ef_co2: Optional[float] = None
    ef_ch4: Optional[float] = None
    ef_n2o: Optional[float] = None
    do_liters: Optional[float] = None
    mass: Optional[float] = None
    gwp: Optional[float] = None
    ef: Optional[float] = None
    liters: Optional[float] = None
    note: Optional[str] = None


class EquipmentRecordResponse(BaseModel):
    id: int
    equipment_id: int
    record_time: datetime
    input_json: dict[str, Any]
    co2e: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
