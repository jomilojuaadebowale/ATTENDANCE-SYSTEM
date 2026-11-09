from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identifier: str
    email: str | None
    full_name: str
    department: str | None
    level: int | None
    role: Role
    is_active: bool
    linked: bool = Field(description="True once the person has signed in and a Firebase UID is linked")
    created_at: datetime


class UserCreate(BaseModel):
    identifier: str = Field(min_length=2, max_length=50, description="Matric number or staff ID")
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    role: Role
    department: str | None = Field(default=None, max_length=120)
    level: int | None = Field(default=None, ge=100, le=900)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    department: str | None = Field(default=None, max_length=120)
    level: int | None = Field(default=None, ge=100, le=900)
    role: Role | None = None
    is_active: bool | None = None


class ImportRowError(BaseModel):
    row: int
    message: str


class ImportResult(BaseModel):
    created: int
    skipped_existing: int
    errors: list[ImportRowError]


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    label: str | None
    is_active: bool
    created_at: datetime


class DeviceBind(BaseModel):
    device_id: str = Field(min_length=8, max_length=128)
    label: str | None = Field(default=None, max_length=120)


class MeOut(UserOut):
    active_device: DeviceOut | None = None
