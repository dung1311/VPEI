#models/user.py
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from core.database import Base

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def vn_now() -> datetime:
    return datetime.now(VN_TZ)


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String, unique=True, index=True, nullable=False)
    email           = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name       = Column(String, nullable=True)
    is_active       = Column(Boolean, default=True)
    is_admin        = Column(Boolean, default=False)
    is_super_admin  = Column(Boolean, default=False, nullable=False)
    created_at      = Column(DateTime(timezone=True), default=vn_now)
    last_login      = Column(DateTime(timezone=True), nullable=True)


class RevokedToken(Base):
    """JWT blacklist. Tokens land here when user is deactivated or deleted."""
    __tablename__ = "revoked_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    jti        = Column(String, unique=True, index=True, nullable=False)
    username   = Column(String, index=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), default=vn_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)