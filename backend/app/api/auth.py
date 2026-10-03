from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, oauth2_scheme
from app.core.security import create_access_token, public_role
from app.db.session import get_db
from app.models.identity import User
from app.schemas.auth import LoginRequest, RegisterRequest, RegisterResponse, Token, UserPublic
from app.services.auth import authenticate_user, register_user, revoke_access_token

router = APIRouter()


def _user_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=public_role(user.role),
        is_active=user.is_active,
    )


async def _read_login(request: Request) -> LoginRequest:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        form = await request.form()
        payload = {
            "email": form.get("username") or form.get("email") or "",
            "password": form.get("password") or "",
        }
    try:
        return LoginRequest.model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> RegisterResponse:
    user = register_user(db, body)
    return RegisterResponse(access_token=create_access_token(user), user=_user_public(user))


@router.post("/login", response_model=Token)
async def login(request: Request, db: Annotated[Session, Depends(get_db)]) -> Token:
    credentials = await _read_login(request)
    user = authenticate_user(db, credentials.email, credentials.password)
    return Token(access_token=create_access_token(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    revoke_access_token(db, token)


@router.get("/me", response_model=UserPublic)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserPublic:
    return _user_public(current_user)
