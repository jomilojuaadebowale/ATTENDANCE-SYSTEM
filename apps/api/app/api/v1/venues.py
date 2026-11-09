from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB, AdminUser, StaffUser
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Venue
from app.schemas.venue import VenueCreate, VenueOut, VenueUpdate
from app.services import audit_service

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=list[VenueOut], summary="List approved lecture venues (staff)")
async def list_venues(user: StaffUser, db: DB) -> list[Venue]:
    return list((await db.execute(select(Venue).order_by(Venue.name))).scalars().all())


@router.post("", response_model=VenueOut, status_code=201, summary="Create a venue (admin)")
async def create_venue(body: VenueCreate, admin: AdminUser, db: DB) -> Venue:
    exists = (await db.execute(select(Venue.id).where(Venue.name == body.name.strip()))).first()
    if exists:
        raise ConflictError("A venue with that name already exists", code="venue_name_taken")
    venue = Venue(
        name=body.name.strip(), latitude=body.latitude, longitude=body.longitude, default_radius_m=body.default_radius_m
    )
    db.add(venue)
    await db.flush()
    audit_service.record(db, actor_id=admin.id, action="venue.create", target_type="venue", target_id=venue.id)
    await db.commit()
    return venue


@router.patch("/{venue_id}", response_model=VenueOut, summary="Update a venue (admin)")
async def update_venue(venue_id: int, body: VenueUpdate, admin: AdminUser, db: DB) -> Venue:
    venue = await db.get(Venue, venue_id)
    if venue is None:
        raise NotFoundError("Venue not found", code="venue_not_found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(venue, k, v)
    audit_service.record(db, actor_id=admin.id, action="venue.update", target_type="venue", target_id=venue.id)
    await db.commit()
    return venue
