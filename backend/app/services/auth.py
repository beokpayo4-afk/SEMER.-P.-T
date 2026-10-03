from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import APIError
from app.core.security import check_password, decode_access_token, hash_password
from app.models.enums import UserRole
from app.models.identity import User
from app.models.revoked_token import RevokedToken
from app.schemas.auth import RegisterRequest


def register_user(db: Session, data: RegisterRequest) -> User:
    existing = db.scalar(select(User).where(User.email == data.email))
    if existing is not None:
        raise APIError(status_code=409, detail="Email is already registered")

    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=UserRole.customer,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(status_code=409, detail="Email is already registered")
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    stored_hash = user.password_hash if user is not None else None
    if not check_password(password, stored_hash) or user is None or not user.is_active:
        raise APIError(status_code=401, detail="Invalid email or password")
    return user


def revoke_access_token(db: Session, token: str) -> None:
    payload = decode_access_token(token)
    jti = str(payload["jti"])
    existing = db.scalar(select(RevokedToken).where(RevokedToken.jti == jti))
    if existing is not None:
        return
    expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
    db.add(RevokedToken(jti=jti, expires_at=expires_at))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
