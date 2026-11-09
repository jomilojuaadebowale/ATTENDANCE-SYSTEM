import pytest
from pydantic import ValidationError

from app.core.auth_providers import DevProvider
from app.core.config import Settings
from app.core.exceptions import UnauthorizedError


def test_dev_auth_is_refused_in_production():
    with pytest.raises(ValidationError):
        Settings(environment="production", auth_provider="dev", _env_file=None)


def test_wildcard_cors_is_refused_in_production():
    with pytest.raises(ValidationError):
        Settings(environment="production", auth_provider="firebase", cors_origins="*", _env_file=None)


def test_dev_provider_accepts_only_dev_tokens():
    assert DevProvider().verify("dev:Ada@Example.edu").email == "ada@example.edu"
    for bad in ("", "Bearer x", "dev:", "eyJhbGciOi..."):
        with pytest.raises(UnauthorizedError):
            DevProvider().verify(bad)
