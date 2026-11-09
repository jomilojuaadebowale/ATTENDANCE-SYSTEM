"""Venue model: lecture halls with GPS coordinates for the geofence check."""

from sqlalchemy import CheckConstraint, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Venue(TimestampMixin, Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)  # e.g. "Amphitheatre 1"
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    default_radius_m: Mapped[int] = mapped_column(Integer, default=75)

    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_venue_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_venue_lng"),
        CheckConstraint("default_radius_m > 0", name="ck_venue_radius_positive"),
    )

    def __repr__(self) -> str:
        return f"<Venue {self.name}>"
