from pydantic import BaseModel
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

class ElectricalItemResponse(BaseModel):
    id: int
    name: str
    power: float
    location: Optional[str]
    entry_date: str
    description: Optional[str]

    class Config:
        from_attributes = True


class ManagerRecordCreate(BaseModel):
    device: str
    kwh: float
    period: str
    from_date: Optional[str] = ""
    to_date: Optional[str] = ""
    note: Optional[str] = ""