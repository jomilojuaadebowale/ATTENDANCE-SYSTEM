import csv
import io

from fastapi import APIRouter, File, Query, UploadFile
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import or_, select

from app.api.deps import DB, AdminUser
from app.api.helpers import count, user_out
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models import Device, Role, User
from app.repositories import user_repo
from app.schemas.common import Page
from app.schemas.user import ImportResult, ImportRowError, UserCreate, UserOut, UserUpdate
from app.services import audit_service

router = APIRouter(prefix="/users", tags=["users (admin)"])
MAX_IMPORT_BYTES = 1_000_000
_email = TypeAdapter(EmailStr)


@router.post("", response_model=UserOut, status_code=201, summary="Create a user (students, lecturers, admins)")
async def create_user(body: UserCreate, admin: AdminUser, db: DB) -> UserOut:
    if await user_repo.get_by_identifier(db, body.identifier):
        raise ConflictError("That matric number / staff ID already exists", code="identifier_taken")
    if await user_repo.get_by_email(db, body.email):
        raise ConflictError("That email is already registered", code="email_taken")
    user = User(
        identifier=body.identifier.strip().upper(),
        email=body.email.lower(),
        full_name=body.full_name.strip(),
        role=body.role,
        department=body.department,
        level=body.level,
    )
    db.add(user)
    await db.flush()
    audit_service.record(
        db,
        actor_id=admin.id,
        action="user.create",
        target_type="user",
        target_id=user.id,
        details={"role": body.role.value},
    )
    await db.commit()
    return user_out(user)


@router.get("", response_model=Page[UserOut], summary="List users with search, role filter and pagination")
async def list_users(
    admin: AdminUser,
    db: DB,
    q: str | None = None,
    role: Role | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> Page[UserOut]:
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.identifier.ilike(like), User.full_name.ilike(like), User.email.ilike(like)))
    total = await count(db, stmt)
    rows = (
        (await db.execute(stmt.order_by(User.identifier).limit(page_size).offset((page - 1) * page_size)))
        .scalars()
        .all()
    )
    return Page(items=[user_out(u) for u in rows], total=total, page=page, page_size=page_size)


@router.post("/import", response_model=ImportResult, summary="Bulk-create users from a CSV file")
async def import_users(admin: AdminUser, db: DB, file: UploadFile = File(...)) -> ImportResult:
    """CSV header: identifier,email,full_name,role,department,level  (department and level optional)."""
    raw = await file.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raise AppError("CSV file is too large (limit 1 MB)", code="file_too_large")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    except UnicodeDecodeError as exc:
        raise AppError("CSV must be UTF-8 encoded", code="bad_encoding") from exc
    required = {"identifier", "email", "full_name", "role"}
    if not reader.fieldnames or not required <= {f.strip() for f in reader.fieldnames}:
        raise AppError(f"CSV must have the columns: {', '.join(sorted(required))}", code="bad_csv_header")

    created, skipped, errors = 0, 0, []
    for line, row in enumerate(reader, start=2):
        try:
            ident = (row.get("identifier") or "").strip().upper()
            email = str(_email.validate_python((row.get("email") or "").strip())).lower()
            name = (row.get("full_name") or "").strip()
            role = Role((row.get("role") or "").strip().lower())
            level_raw = (row.get("level") or "").strip()
            level = int(level_raw) if level_raw else None
            if len(ident) < 2 or len(name) < 2:
                raise ValueError("identifier and full_name are required")
        except (ValueError, ValidationError) as exc:
            errors.append(ImportRowError(row=line, message=str(exc).splitlines()[0]))
            continue
        if await user_repo.get_by_identifier(db, ident) or await user_repo.get_by_email(db, email):
            skipped += 1
            continue
        db.add(
            User(
                identifier=ident,
                email=email,
                full_name=name,
                role=role,
                department=(row.get("department") or "").strip() or None,
                level=level,
            )
        )
        created += 1
    audit_service.record(
        db,
        actor_id=admin.id,
        action="user.import",
        target_type="user",
        target_id="bulk",
        details={"created": created, "skipped": skipped, "errors": len(errors)},
    )
    await db.commit()
    return ImportResult(created=created, skipped_existing=skipped, errors=errors)


@router.get("/{user_id}", response_model=UserOut, summary="Get one user")
async def get_user(user_id: int, admin: AdminUser, db: DB) -> UserOut:
    user = await user_repo.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found", code="user_not_found")
    return user_out(user)


@router.patch("/{user_id}", response_model=UserOut, summary="Update a user (role, active flag, profile)")
async def update_user(user_id: int, body: UserUpdate, admin: AdminUser, db: DB) -> UserOut:
    user = await user_repo.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found", code="user_not_found")
    changes = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (
        changes.get("is_active") is False or changes.get("role") not in (None, Role.SUPER_ADMIN)
    ):
        raise ConflictError("You cannot disable or demote your own account", code="self_lockout")
    before = {k: getattr(user, k) for k in changes}
    for k, v in changes.items():
        setattr(user, k, v)
    audit_service.record(
        db,
        actor_id=admin.id,
        action="user.update",
        target_type="user",
        target_id=user.id,
        details={
            "before": {k: getattr(v, "value", v) for k, v in before.items()},
            "after": {k: getattr(v, "value", v) for k, v in changes.items()},
        },
    )
    await db.commit()
    return user_out(user)


@router.post("/{user_id}/reset-device", status_code=204, summary="Unbind a student's phone so they can bind a new one")
async def reset_device(user_id: int, admin: AdminUser, db: DB) -> None:
    user = await user_repo.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found", code="user_not_found")
    device: Device | None = await user_repo.get_active_device(db, user_id)
    if device is not None:
        device.is_active = False
    audit_service.record(
        db,
        actor_id=admin.id,
        action="device.reset",
        target_type="user",
        target_id=user_id,
        details={"device_id": device.device_id if device else None},
    )
    await db.commit()
