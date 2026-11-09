from fastapi import APIRouter

from app.api.v1 import attendance, auth, courses, reports, sessions, users, venues

api_router = APIRouter()
for module in (auth, users, courses, venues, sessions, attendance, reports):
    api_router.include_router(module.router)
