"""Application settings, loaded from environment variables (and a local .env in dev)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore")

    # --- general ---
    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "University Attendance API"
    api_prefix: str = "/api/v1"
    # Comma-separated list of allowed browser origins (the Next.js app URL).
    cors_origins: str = "http://localhost:3000"

    # --- database ---
    database_url: str = "postgresql+asyncpg://attendance:attendance_dev@localhost:5432/attendance"

    # --- authentication ---
    # "firebase": verify Firebase ID tokens (production).
    # "dev": accept `dev:<email>` tokens. Local development and tests ONLY.
    auth_provider: Literal["firebase", "dev"] = "firebase"
    firebase_project_id: str | None = None
    # Path to a service-account JSON file, or the JSON itself (e.g. from a secret manager).
    firebase_credentials_path: str | None = None
    firebase_credentials_json: str | None = None

    # --- academic calendar defaults ---
    current_academic_year: str = "2026/2027"
    current_semester: int = Field(default=1, ge=1, le=2)

    # --- QR / session rules ---
    qr_slot_seconds: int = Field(default=20, ge=5, le=120)
    # Allowed difference between the phone's clock and the QR slot window.
    clock_skew_tolerance_seconds: int = Field(default=60, ge=0, le=600)
    # Syncs that arrive later than this after the scan are treated as "offline" scans.
    online_sync_window_seconds: int = Field(default=120, ge=0)
    # Offline scans are still trusted for this long after the session ends.
    sync_grace_minutes: int = Field(default=60, ge=0)
    max_session_minutes: int = Field(default=300, ge=5)

    # --- geofence ---
    default_radius_m: int = Field(default=75, ge=5, le=1000)
    # Scans with worse GPS accuracy than this are flagged for lecturer review.
    max_accuracy_m: float = Field(default=100.0, gt=0)

    # Minimum attendance percentage treated as "eligible" in reports (typical exam rule).
    attendance_threshold_percent: float = Field(default=75.0, ge=0, le=100)

    # --- manual corrections ---
    # Lecturers may edit/mark attendance for this long after a session ends.
    correction_window_hours: int = Field(default=24, ge=0)

    # --- rate limiting (requests per window, per authenticated user or IP) ---
    rate_limit_enabled: bool = True
    sync_rate_limit: int = 60
    sync_rate_window_seconds: int = 60
    auth_rate_limit: int = 30
    auth_rate_window_seconds: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _refuse_dev_auth_in_production(self) -> "Settings":
        if self.environment == "production" and self.auth_provider == "dev":
            raise ValueError("AUTH_PROVIDER=dev is not allowed when ENVIRONMENT=production")
        if self.environment == "production" and "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS must not contain '*' in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
