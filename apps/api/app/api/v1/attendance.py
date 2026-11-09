from fastapi import APIRouter, Depends, Query

from app.api.deps import DB, SettingsDep, StaffUser, StudentUser
from app.core.rate_limit import sync_limiter
from app.schemas.attendance import (
    AttendanceOut,
    MyAttendanceOut,
    ReviewRequest,
    SyncRequest,
    SyncResponse,
)
from app.schemas.common import Page
from app.services import attendance_service, correction_service, report_service

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post(
    "/sync",
    response_model=SyncResponse,
    dependencies=[Depends(sync_limiter)],
    summary="Submit one or more scans (live or queued offline). Safe to retry.",
)
async def sync(body: SyncRequest, student: StudentUser, db: DB, settings: SettingsDep) -> SyncResponse:
    results = []
    for scan in body.scans:
        results.append(await attendance_service.process_scan(db, student, scan, settings))
    return SyncResponse(results=results)


@router.get("/me", response_model=Page[MyAttendanceOut], summary="My attendance history")
async def my_history(
    student: StudentUser, db: DB, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)
) -> Page[MyAttendanceOut]:
    items, total = await report_service.my_history(db, student, page_size, (page - 1) * page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/{attendance_id}/review", response_model=AttendanceOut, summary="Approve or reject a flagged scan")
async def review(
    attendance_id: int, body: ReviewRequest, user: StaffUser, db: DB, settings: SettingsDep
) -> AttendanceOut:
    record = await correction_service.review_flagged(db, user, attendance_id, body, settings)
    return AttendanceOut.model_validate(record)
