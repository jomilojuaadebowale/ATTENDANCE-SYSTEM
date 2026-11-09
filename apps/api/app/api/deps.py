"""Shared FastAPI dependencies: database session, authentication and role checks.

Authentication  = who are you?  -> Firebase ID token (verified by an AuthProvider)
Authorization   = what may you do? -> `users.role` in OUR database, checked on the server.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_providers import AuthProvider, get_auth_provider
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.models import Role, User
from app.repositories import user_repo
from app.services import audit_service

bearer = HTTPBearer(auto_error=False, description="Firebase ID token")

DB = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    provider: Annotated[AuthProvider, Depends(get_auth_provider)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing bearer token", code="missing_token")
    claims = provider.verify(credentials.credentials)

    user = await user_repo.get_by_firebase_uid(db, claims.uid)
    if user is None and claims.email and claims.email_verified:
        # First sign-in: link the Firebase account to the user the admin pre-created.
        candidate = await user_repo.get_by_email(db, claims.email)
        if candidate is not None and candidate.firebase_uid is None:
            candidate.firebase_uid = claims.uid
            audit_service.record(
                db, actor_id=candidate.id, action="user.link_firebase", target_type="user", target_id=candidate.id
            )
            await db.commit()
            user = candidate
    if user is None:
        raise ForbiddenError(
            "Your account has not been set up. Contact your department administrator.",
            code="account_not_provisioned",
        )
    if not user.is_active:
        raise ForbiddenError("Your account is disabled.", code="account_disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[..., User]:
    allowed = set(roles)

    async def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError("You do not have permission to do this.", code="insufficient_role")
        return user

    return checker


AdminUser = Annotated[User, Depends(require_roles(Role.SUPER_ADMIN))]
StaffUser = Annotated[User, Depends(require_roles(Role.LECTURER, Role.SUPER_ADMIN))]
StudentUser = Annotated[User, Depends(require_roles(Role.STUDENT))]
