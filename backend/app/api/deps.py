import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import APIError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.identity import User
from app.models.revoked_token import RevokedToken

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    payload = decode_access_token(token)
    jti = str(payload["jti"])
    revoked = db.scalar(select(RevokedToken.id).where(RevokedToken.jti == jti))
    if revoked is not None:
        raise APIError(status_code=401, detail="Could not validate credentials")
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError as exc:
        raise APIError(status_code=401, detail="Could not validate credentials") from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise APIError(status_code=401, detail="Could not validate credentials")
    return user


def get_optional_user(
    token: Annotated[str | None, Depends(oauth2_scheme_optional)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    if token is None:
        return None
    try:
        return get_current_user(token, db)
    except APIError as exc:
        if exc.status_code == 401:
            return None
        raise


def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role != UserRole.admin:
        raise APIError(status_code=403, detail="Admin access required")
    return current_user


def require_customer(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role != UserRole.customer:
        raise APIError(status_code=403, detail="Customer access required")
    return current_user
