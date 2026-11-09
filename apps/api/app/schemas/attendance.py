import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AttendanceStatus, FlagReason, ManualReason


class ScanIn(BaseModel):
    client_uuid: uuid.UUID = Field(description="Generated on the phone at scan time; makes retries idempotent")
    qr_payload: str = Field(min_length=1, max_length=300)
    device_id: str = Field(min_length=8, max_length=128)
    device_time: datetime = Field(description="When the phone scanned (timezone-aware)")
    scan_lat: float | None = None
    scan_lng: float | None = None
    accuracy_m: float | None = Field(default=None, ge=0)


class SyncRequest(BaseModel):
    scans: list[ScanIn] = Field(min_length=1, max_length=100)


ScanOutcome = Literal["recorded", "flagged", "duplicate", "rejected"]


class ScanResult(BaseModel):
    client_uuid: uuid.UUID
    outcome: ScanOutcome
    code: str = Field(description="Machine-readable reason, e.g. verified, outside_radius, qr_expired")
    message: str
    attendance_status: AttendanceStatus | None = None
    flag_reason: FlagReason | None = None
    distance_m: float | None = None
    session_id: uuid.UUID | None = None
    course_code: str | None = None


class SyncResponse(BaseModel):
    results: list[ScanResult]


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: uuid.UUID
    student_id: int
    status: AttendanceStatus
    flag_reason: FlagReason | None
    manual_reason: ManualReason | None
    distance_m: float | None
    accuracy_m: float | None
    device_time: datetime | None
    received_at: datetime
    marked_by_id: int | None


class MyAttendanceOut(BaseModel):
    id: int
    session_id: uuid.UUID
    course_code: str
    course_title: str
    session_starts_at: datetime
    status: AttendanceStatus
    flag_reason: FlagReason | None
    marked_manually: bool
    received_at: datetime


class RosterEntry(BaseModel):
    student_id: int
    identifier: str
    full_name: str
    # "not_marked" means no record exists (yet). It is NOT "absent" until the session is closed.
    status: AttendanceStatus | Literal["not_marked"]
    attendance_id: int | None = None
    flag_reason: FlagReason | None = None
    manual_reason: ManualReason | None = None
    distance_m: float | None = None
    received_at: datetime | None = None


class SessionRoster(BaseModel):
    session_id: uuid.UUID
    session_status: str
    counts: dict[str, int]
    entries: list[RosterEntry]


class ManualMarkRequest(BaseModel):
    identifiers: list[str] = Field(min_length=1, max_length=500, description="Matric numbers")
    reason: ManualReason
    note: str | None = Field(default=None, max_length=500)


class ManualMarkResult(BaseModel):
    marked: list[str]
    already_present: list[str]
    not_enrolled: list[str]


class ReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=500)
