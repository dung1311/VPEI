# schemas/scope1_dashboard.py
from pydantic import BaseModel
from typing import List, Optional

class KPICard(BaseModel):
    total_fuel: float         
    total_co2e: float       
    top_emitter_name: str     
    top_emitter_co2e: float   
    mom_growth: float         # 

class ChartData(BaseModel):
    labels: List[str]
    values: List[float]

class TableRow(BaseModel):
    device_name: str
    fuel_type: str
    consumption: float
    total_co2e: float
    percentage: float

class DashboardResponse(BaseModel):
    kpis: KPICard
    bar_chart: ChartData
    line_chart: ChartData
    table_data: List[TableRow]