import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.exceptions import APIError
from app.models.enums import UserRole
from app.models.identity import User

password_hasher = PasswordHash.recommended()
_DUMMY_PASSWORD_HASH = password_hasher.hash("dummy-password-not-used")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except Exception:
        return False


def check_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return False
    return verify_password(password, password_hash)


def create_access_token(user: User) -> str:
    if not settings.secret_key:
        raise APIError(status_code=500, detail="Authentication is not configured")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    if not settings.secret_key:
        raise APIError(status_code=500, detail="Authentication is not configured")
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise APIError(status_code=401, detail="Could not validate credentials") from exc
    if payload.get("type") != "access" or not payload.get("sub") or not payload.get("jti"):
        raise APIError(status_code=401, detail="Could not validate credentials")
    return payload


def public_role(role: UserRole) -> Literal["CUSTOMER", "ADMIN"]:
    if role == UserRole.admin:
        return "ADMIN"
    return "CUSTOMER"
