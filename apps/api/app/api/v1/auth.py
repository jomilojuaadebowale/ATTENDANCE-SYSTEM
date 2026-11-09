from fastapi import APIRouter, Depends

from app.api.deps import DB, CurrentUser, StudentUser
from app.api.helpers import user_out
from app.core.exceptions import ConflictError
from app.core.rate_limit import auth_limiter
from app.models import Device
from app.repositories import user_repo
from app.schemas.user import DeviceBind, DeviceOut, MeOut
from app.services import audit_service

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(auth_limiter)])


@router.get("/me", response_model=MeOut, summary="The signed-in user's profile and bound device")
async def me(user: CurrentUser, db: DB) -> MeOut:
    device = await user_repo.get_active_device(db, user.id)
    return MeOut(**user_out(user).model_dump(), active_device=DeviceOut.model_validate(device) if device else None)


@router.post("/device", response_model=DeviceOut, status_code=201, summary="Bind this phone to the student's account")
async def bind_device(body: DeviceBind, user: StudentUser, db: DB) -> DeviceOut:
    existing = await user_repo.get_active_device(db, user.id)
    if existing is not None:
        if existing.device_id == body.device_id:
            return DeviceOut.model_validate(existing)
        raise ConflictError(
            "A different device is already bound to your account. Ask an administrator to reset it.",
            code="device_already_bound",
        )
    if await user_repo.device_used_by_others(db, body.device_id, user.id):
        raise ConflictError("This device is bound to another account.", code="device_in_use")
    device = Device(user_id=user.id, device_id=body.device_id, label=body.label, is_active=True)
    db.add(device)
    audit_service.record(db, actor_id=user.id, action="device.bind", target_type="user", target_id=user.id)
    await db.commit()
    return DeviceOut.model_validate(device)
