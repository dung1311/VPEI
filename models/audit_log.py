from sqlalchemy import Column, Integer, String, DateTime
from core.database import Base
from models.user import vn_now

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    action = Column(String, nullable=False)
    description = Column(String, nullable=True)
    month_year = Column(String, index=True, nullable=False) # e.g., "03/2026"
    created_at = Column(DateTime(timezone=True), default=vn_now)
    scope = Column(String, index=True, nullable=True)  # e.g., "scope2", "scope3"
