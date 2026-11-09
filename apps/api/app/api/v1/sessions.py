import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DB, SettingsDep, StaffUser
from app.api.helpers import count, session_out
from app.models import ClassSession, Role, SessionStatus
from app.schemas.attendance import ManualMarkRequest, ManualMarkResult, SessionRoster
from app.schemas.common import Page
from app.schemas.session import QRSeedOut, QRTokenOut, SessionCreate, SessionOut
from app.services import access, correction_service, report_service, session_service

router = APIRouter(prefix="/sessions", tags=["attendance sessions"])


@router.post(
    "", response_model=SessionOut, status_code=201, summary="Open an attendance session for a course you teach"
)
async def create_session(body: SessionCreate, user: StaffUser, db: DB, settings: SettingsDep) -> SessionOut:
    session = await session_service.create_session(db, user, body, settings)
    return await session_out(db, session)


@router.get("", response_model=Page[SessionOut], summary="List sessions (lecturers: their courses only)")
async def list_sessions(
    user: StaffUser,
    db: DB,
    course_id: int | None = None,
    status: SessionStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> Page[SessionOut]:
    stmt = select(ClassSession)
    if user.role == Role.LECTURER:
        stmt = stmt.where(ClassSession.lecturer_id == user.id)
    if course_id:
        stmt = stmt.where(ClassSession.course_id == course_id)
    if status:
        stmt = stmt.where(ClassSession.status == status)
    total = await count(db, stmt)
    rows = (
        (await db.execute(stmt.order_by(ClassSession.starts_at.desc()).limit(page_size).offset((page - 1) * page_size)))
        .scalars()
        .all()
    )
    items = [await session_out(db, await session_service.refresh_status(db, s)) for s in rows]
    return Page(items=items, total=total, page=page, page_size=page_size)


async def _staff_session(db, user, session_id: uuid.UUID) -> ClassSession:
    session = await session_service.get_session_or_404(db, session_id)
    await access.require_session_staff(db, user, session)
    return session


@router.get("/{session_id}", response_model=SessionOut, summary="One session")
async def get_session(session_id: uuid.UUID, user: StaffUser, db: DB) -> SessionOut:
    return await session_out(db, await _staff_session(db, user, session_id))


@router.get("/{session_id}/qr", response_model=QRTokenOut, summary="Current rotating QR payload (server-issued)")
async def get_qr(session_id: uuid.UUID, user: StaffUser, db: DB) -> QRTokenOut:
    return session_service.current_qr(await _staff_session(db, user, session_id))


@router.get(
    "/{session_id}/qr-seed",
    response_model=QRSeedOut,
    summary="Signing seed so the lecturer's device can render QR codes offline",
)
async def get_qr_seed(session_id: uuid.UUID, user: StaffUser, db: DB) -> QRSeedOut:
    return session_service.qr_seed(await _staff_session(db, user, session_id))


@router.post("/{session_id}/close", response_model=SessionOut, summary="Close (finalize) a session now")
async def close_session(session_id: uuid.UUID, user: StaffUser, db: DB) -> SessionOut:
    session = await session_service.get_session_or_404(db, session_id)
    return await session_out(db, await session_service.close_session(db, user, session))


@router.post("/{session_id}/cancel", response_model=SessionOut, summary="Cancel a session (ignored by reports)")
async def cancel_session(session_id: uuid.UUID, user: StaffUser, db: DB) -> SessionOut:
    session = await session_service.get_session_or_404(db, session_id)
    return await session_out(db, await session_service.cancel_session(db, user, session))


@router.get(
    "/{session_id}/roster", response_model=SessionRoster, summary="Enrolled students with their attendance status"
)
async def roster(session_id: uuid.UUID, user: StaffUser, db: DB) -> SessionRoster:
    return await report_service.session_roster(db, await _staff_session(db, user, session_id))


@router.post(
    "/{session_id}/attendance/manual",
    response_model=ManualMarkResult,
    summary="Mark students present manually (no phone, dead battery, ...)",
)
async def manual_mark(
    session_id: uuid.UUID, body: ManualMarkRequest, user: StaffUser, db: DB, settings: SettingsDep
) -> ManualMarkResult:
    session = await session_service.get_session_or_404(db, session_id)
    return await correction_service.manual_mark(db, user, session, body, settings)
