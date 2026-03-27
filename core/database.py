# core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite only
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and seed the super admin account."""
    # Import models so SQLAlchemy registers them before create_all
    from models import user as _  # noqa: F401
    from models import scope1 as _  # noqa: F401
    
    from models import electrical_item as _  # noqa: F401
    from models import audit_log as _  # noqa: F401

    Base.metadata.create_all(bind=engine)

    from models.user import User
    from core.security import hash_password

    SUPER_ADMIN_USERNAME = "vpeiadmin"

    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == SUPER_ADMIN_USERNAME).first()
        if not exists:
            admin = User(
                username=SUPER_ADMIN_USERNAME,
                email="admin@vpei.vn",
                hashed_password=hash_password("123123123"),
                full_name="VPEI Super Administrator",
                is_active=True,
                is_admin=True,
            )
            db.add(admin)
            db.commit()
            print(f"✅ Seeded super admin: {SUPER_ADMIN_USERNAME} / 123123123")
    finally:
        db.close()