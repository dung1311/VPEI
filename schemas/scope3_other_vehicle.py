from pydantic import BaseModel


class Scope3OtherVehicleCreate(BaseModel):
    vehicle_type: str
    name: str
    period: str
    trips: int
    consumption: float
    note: str | None = None
