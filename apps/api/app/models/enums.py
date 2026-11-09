"""All enums used by the models, in one place."""

import enum


class Role(str, enum.Enum):
    STUDENT = "student"
    LECTURER = "lecturer"
    SUPER_ADMIN = "super_admin"


class SessionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class AttendanceStatus(str, enum.Enum):
    VERIFIED = "verified"  # passed all checks
    FLAGGED = "flagged"  # needs lecturer review (see flag_reason)
    REJECTED = "rejected"  # failed hard checks (bad signature, outside window)
    MANUAL = "manual"  # marked by a lecturer


class FlagReason(str, enum.Enum):
    NO_LOCATION = "no_location"
    LOW_ACCURACY = "low_accuracy"
    OUTSIDE_RADIUS = "outside_radius"
    LATE_SYNC = "late_sync"
    CLOCK_SKEW = "clock_skew"
    DEVICE_MISMATCH = "device_mismatch"
    SHARED_DEVICE = "shared_device"
    BAD_SIGNATURE = "bad_signature"
    OUTSIDE_TIME_WINDOW = "outside_time_window"


class ManualReason(str, enum.Enum):
    NO_PHONE = "no_phone"
    PHONE_DEAD = "phone_dead"
    NETWORK_FAILURE = "network_failure"
    APP_PROBLEM = "app_problem"
    OTHER = "other"
