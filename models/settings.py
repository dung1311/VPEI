from sqlalchemy import Column, Integer, String
from core.database import Base

class CompanySetting(Base):
    __tablename__ = "company_settings"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=True)
    tax_code = Column(String(100), nullable=True)
    address = Column(String(500), nullable=True)
    logo_src = Column(String(1000), nullable=True)
