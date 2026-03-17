from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from core.database import Base

# The one and only super admin — cannot be deleted or locked by anyone
SUPER_ADMIN_USERNAME = "vpeiadmin"


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String, unique=True, index=True, nullable=False)
    email           = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name       = Column(String, nullable=True)
    is_active       = Column(Boolean, default=True)
    is_admin        = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=datetime.utcnow)
    last_login      = Column(DateTime, nullable=True)


class RevokedToken(Base):
    """JWT blacklist. Tokens land here when user is deactivated or deleted."""
    __tablename__ = "revoked_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    jti        = Column(String, unique=True, index=True, nullable=False)
    username   = Column(String, index=True, nullable=False)
    revoked_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)