from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
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
    """Tạo bảng và (nếu cần) seed tài khoản super admin từ .env."""
    from models import user as _  # noqa: F401
    from models import device as _  # noqa: F401
    from models import electrical_item as _  # noqa: F401
    from models import audit_log as _  # noqa: F401
    from models import container as _  # noqa: F401
    from models import ship as _  # noqa: F401
    from models import harbor_craft as _  # noqa: F401

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if "audit_logs" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("audit_logs")]
        if "scope" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE audit_logs ADD COLUMN scope VARCHAR DEFAULT NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_scope ON audit_logs (scope)"))

    from models.user import User
    from core.security import hash_password

    uname = settings.vpei_superadmin_username
    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == uname).first()
        if not exists:
            admin = User(
                username=uname,
                email=settings.vpei_superadmin_email,
                hashed_password=hash_password(settings.vpei_superadmin_password),
                full_name=settings.vpei_superadmin_full_name,
                is_active=True,
                is_admin=True,
            )
            db.add(admin)
            db.commit()
            print(f"✅ Đã tạo super admin: {uname} (email: {settings.vpei_superadmin_email})")
    finally:
        db.close()
