import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import SessionStatus


class SessionCreate(BaseModel):
    course_id: int
    venue_id: int | None = None
    # Lecturer's current position. Optional second geofence anchor; required without a venue.
    start_lat: float | None = Field(default=None, ge=-90, le=90)
    start_lng: float | None = Field(default=None, ge=-180, le=180)
    starts_at: datetime | None = Field(default=None, description="Defaults to now (UTC)")
    duration_minutes: int = Field(default=60, ge=5, le=600)
    radius_m: int | None = Field(default=None, ge=5, le=1000)
    slot_seconds: int | None = Field(default=None, ge=5, le=120)

    @model_validator(mode="after")
    def _need_an_anchor(self) -> "SessionCreate":
        has_start = self.start_lat is not None and self.start_lng is not None
        if self.venue_id is None and not has_start:
            raise ValueError("Provide a venue_id or the lecturer's start_lat/start_lng")
        if (self.start_lat is None) != (self.start_lng is None):
            raise ValueError("start_lat and start_lng must be provided together")
        return self


class SessionOut(BaseModel):
    """Never includes the signing secret."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: int
    lecturer_id: int
    venue_id: int | None
    academic_year: str
    semester: int
    start_lat: float | None
    start_lng: float | None
    radius_m: int
    slot_seconds: int
    starts_at: datetime
    ends_at: datetime
    status: SessionStatus
    course_code: str | None = None
    venue_name: str | None = None
    attendance_count: int | None = None


class QRTokenOut(BaseModel):
    payload: str
    slot: int
    slot_seconds: int
    valid_from: datetime
    valid_until: datetime
    server_time: datetime


class QRSeedOut(BaseModel):
    """Lets the lecturer's device generate the rotating QR locally, even with no network."""

    session_id: uuid.UUID
    secret: str
    starts_at: datetime
    ends_at: datetime
    slot_seconds: int
    server_time: datetime
