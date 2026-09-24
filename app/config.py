from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    biotime_base_url: str = "http://127.0.0.1:80"
    biotime_username: str
    biotime_password: str
    # "Token" (long-lived) or "JWT" (short-lived, re-authenticate on 401)
    biotime_auth_scheme: str = "JWT"

    database_url: str

    sync_enabled: bool = True
    sync_interval_minutes: int = 15


settings = Settings()
