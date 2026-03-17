from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "VPEI"
    secret_key: str = "CHANGE_ME_IN_PRODUCTION_USE_RANDOM_32BYTE_STRING"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    database_url: str = "sqlite:///./vpei.db"

    # Gmail SMTP
    # Setup: Google Account → Security → 2-Step Verification → App passwords
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""       # 16-char App Password, spaces optional
    smtp_from_name: str = "VPEI System"
    smtp_enabled: bool = False    # flip to True after filling credentials above

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()