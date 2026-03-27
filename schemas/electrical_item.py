from pydantic import BaseModel, Field
from typing import Optional

class ElectricalItemCreate(BaseModel):
    name: str
    power: float
    location: str
    entry_date: str
    description: Optional[str] = None


class ElectricalItemUpdate(BaseModel):
    name: str
    power: float
    location: str
    entry_date: str
    description: Optional[str] = None
    update_reason: str = Field(..., min_length=3)

class ElectricalItemResponse(BaseModel):
    id: int
    name: str
    power: float
    location: Optional[str]
    entry_date: str
    description: Optional[str]

    class Config:
        from_attributes = True