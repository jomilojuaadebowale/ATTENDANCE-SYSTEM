"""Identity providers: turn a bearer token into verified identity claims.

* FirebaseProvider  - production. Verifies Firebase ID tokens with firebase-admin.
* DevProvider       - local development and tests ONLY. Accepts `dev:<email>`.
                      Settings refuse to load it when ENVIRONMENT=production.

The provider only proves WHO the caller is. What they may do is decided by the
`users.role` column in our own database (see app/api/deps.py).
"""

import json
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError


@dataclass(frozen=True)
class IdentityClaims:
    uid: str
    email: str | None
    email_verified: bool


class AuthProvider(Protocol):
    def verify(self, token: str) -> IdentityClaims: ...


class DevProvider:
    PREFIX = "dev:"

    def verify(self, token: str) -> IdentityClaims:
        if not token.startswith(self.PREFIX) or len(token) <= len(self.PREFIX):
            raise UnauthorizedError("Invalid development token", code="invalid_token")
        email = token[len(self.PREFIX) :].strip().lower()
        return IdentityClaims(uid=f"dev-{email}", email=email, email_verified=True)


class FirebaseProvider:
    def __init__(self, settings: Settings):
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            if settings.firebase_credentials_json:
                cred = credentials.Certificate(json.loads(settings.firebase_credentials_json))
            elif settings.firebase_credentials_path:
                cred = credentials.Certificate(settings.firebase_credentials_path)
            else:
                cred = credentials.ApplicationDefault()
            options = {"projectId": settings.firebase_project_id} if settings.firebase_project_id else None
            firebase_admin.initialize_app(cred, options)

    def verify(self, token: str) -> IdentityClaims:
        from firebase_admin import auth

        try:
            decoded = auth.verify_id_token(token, check_revoked=False)
        except Exception as exc:  # firebase_admin raises several distinct types
            raise UnauthorizedError("Invalid or expired token", code="invalid_token") from exc
        return IdentityClaims(
            uid=decoded["uid"],
            email=(decoded.get("email") or "").lower() or None,
            email_verified=bool(decoded.get("email_verified")),
        )


_provider: AuthProvider | None = None


def get_auth_provider() -> AuthProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        _provider = DevProvider() if settings.auth_provider == "dev" else FirebaseProvider(settings)
    return _provider


def reset_auth_provider() -> None:
    global _provider
    _provider = None
