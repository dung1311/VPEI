from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = 'VPEI'
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    database_url: str

    # Gmail SMTP
    # Setup: Google Account → Security → 2-Step Verification → App passwords
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str       # 16-char App Password, spaces optional
    smtp_from_name: str
    smtp_enabled: bool

    # Seed super admin khi khởi tạo DB (chỉ tạo nếu chưa có user trùng username)
    vpei_superadmin_username: str = "vpeiadmin"
    vpei_superadmin_password: str = "123123123"
    vpei_superadmin_email: str = "vpeiadmin@gmail.com"
    vpei_superadmin_full_name: str = "VPEI Super Administrator"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()