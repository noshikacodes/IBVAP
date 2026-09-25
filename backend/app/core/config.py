from typing import List, Union, Dict
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ALERT_PRIORITY_POLICY: Dict[str, str] = {
    "intrusion": "critical",
    "tripwire_crossing": "high",
    "loitering": "medium",
    "zone_exit": "low",
    "anpr_watchlist_hit": "critical",
    "anpr_unregistered": "high",
    "anpr_detection": "low",
    "frs_watchlist_hit": "critical",
    "frs_unregistered": "medium",
    "frs_identification": "low",
}


class Settings(BaseSettings):
    PROJECT_NAME: str = "IBVAP - Intelligent Border Video Analytics Platform"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS Origins
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Messaging & Redis Settings (Phase 3B)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ALERT_CHANNEL: str = "ibvap.alerts"
    ALERT_COOLDOWN_SECONDS: float = 30.0
    MAX_IN_MEMORY_ALERTS: int = 1000
    ALERT_PRIORITY_POLICY: Dict[str, str] = DEFAULT_ALERT_PRIORITY_POLICY

    # Database & Storage
    DATABASE_URL: str = "sqlite+aiosqlite:///./ibvap.db"
    MEDIAMTX_RTSP_URL: str = "rtsp://localhost:8554"
    STORAGE_DIR: str = "./storage"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
