from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Optional: normally entered once on the /setup page and saved in the
    # database. If set here and nothing has been saved yet, these are used.
    biotime_base_url: str = ""
    biotime_username: str = ""
    biotime_password: str = ""
    # "Token" (long-lived) or "JWT" (short-lived, re-authenticate on 401)
    biotime_auth_scheme: str = "JWT"

    # SQLite file next to the app by default; set a postgresql+pg8000:// URL to use Postgres instead.
    database_url: str = "sqlite:///./biotime.db"

    # Let systems on other computers (an ERP, payroll) call the client API.
    # start-server.bat reads this and listens on the network instead of only
    # on this PC. Pages stay local-only either way; see app/api_keys.py.
    api_network_access: bool = False

    sync_enabled: bool = True
    sync_interval_minutes: int = 15

    # Work schedule used by the attendance reports (worked hours / absence /
    # late arrivals). BioTime doesn't expose shift assignments over its REST
    # API, so the expected schedule is configured here for everyone.
    shift_start: str = "08:00"
    shift_end: str = "17:00"
    shift_break_minutes: int = 60
    # Weekdays that are scheduled workdays, 0=Monday ... 6=Sunday
    shift_work_days: str = "0,1,2,3,4"
    late_grace_minutes: int = 0


settings = Settings()
