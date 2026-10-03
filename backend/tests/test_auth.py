import uuid
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_customer
from app.core.config import settings
from app.main import app
from app.models.enums import UserRole
from app.models.identity import User

probe_router = APIRouter()


@probe_router.get("/admin")
def admin_probe(_: Annotated[User, Depends(require_admin)]) -> dict[str, bool]:
    return {"ok": True}


@probe_router.get("/customer")
def customer_probe(_: Annotated[User, Depends(require_customer)]) -> dict[str, bool]:
    return {"ok": True}


app.include_router(probe_router, prefix="/api/test-auth")


def _email() -> str:
    return f"user-{uuid.uuid4().hex}@example.com"


def _register_body(email: str, password: str = "Password1", full_name: str = "Asha Rao") -> dict[str, str]:
    return {"email": email, "password": password, "full_name": full_name}


def _token(client: TestClient, email: str, password: str = "Password1") -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_register_returns_customer_token_without_password_hash(client: TestClient, db_session: Session) -> None:
    email = _email()
    response = client.post("/api/auth/register", json=_register_body(f"  {email.upper()}  "))

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == email
    assert body["user"]["role"] == "CUSTOMER"
    assert body["user"]["full_name"] == "Asha Rao"
    assert "password_hash" not in response.text
    assert "password" not in body["user"]

    stored = db_session.scalar(select(User).where(User.email == email))
    assert stored is not None
    assert stored.password_hash != "Password1"
    assert stored.role == UserRole.customer


def test_register_rejects_invalid_email_short_password_and_duplicate(client: TestClient) -> None:
    invalid_email = client.post("/api/auth/register", json=_register_body("not-an-email"))
    assert invalid_email.status_code == 422

    short_password = client.post("/api/auth/register", json=_register_body(_email(), password="short1"))
    assert short_password.status_code == 422

    letters_only = client.post("/api/auth/register", json=_register_body(_email(), password="longpassword"))
    assert letters_only.status_code == 422

    email = _email()
    first = client.post("/api/auth/register", json=_register_body(email))
    assert first.status_code == 201
    duplicate = client.post("/api/auth/register", json=_register_body(email.upper()))
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Email is already registered"


def test_register_ignores_attempt_to_choose_admin_role(client: TestClient, db_session: Session) -> None:
    email = _email()
    payload = _register_body(email)
    payload["role"] = "ADMIN"
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json()["user"]["role"] == "CUSTOMER"
    stored = db_session.scalar(select(User).where(User.email == email))
    assert stored is not None
    assert stored.role == UserRole.customer


def test_login_accepts_json_and_form_and_hides_invalid_credentials(client: TestClient) -> None:
    email = _email()
    client.post("/api/auth/register", json=_register_body(email))

    json_login = client.post("/api/auth/login", json={"email": email, "password": "Password1"})
    assert json_login.status_code == 200
    assert json_login.json()["token_type"] == "bearer"
    assert "password_hash" not in json_login.text

    form_login = client.post("/api/auth/login", data={"username": email, "password": "Password1"})
    assert form_login.status_code == 200

    wrong_password = client.post("/api/auth/login", json={"email": email, "password": "Wrongpass1"})
    unknown_email = client.post("/api/auth/login", json={"email": _email(), "password": "Wrongpass1"})
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"] == "Invalid email or password"


def test_inactive_user_cannot_login(client: TestClient, db_session: Session) -> None:
    email = _email()
    client.post("/api/auth/register", json=_register_body(email))
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_active = False
    db_session.commit()

    response = client.post("/api/auth/login", json={"email": email, "password": "Password1"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_me_requires_a_valid_token_and_logout_revokes_it(client: TestClient) -> None:
    email = _email()
    registered = client.post("/api/auth/register", json=_register_body(email))
    token = registered.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    missing = client.get("/api/auth/me")
    assert missing.status_code == 401

    invalid = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert invalid.status_code == 401

    current = client.get("/api/auth/me", headers=headers)
    assert current.status_code == 200
    assert current.json()["email"] == email
    assert current.json()["role"] == "CUSTOMER"
    assert "password_hash" not in current.text

    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 204

    after_logout = client.get("/api/auth/me", headers=headers)
    assert after_logout.status_code == 401


def test_expired_token_is_rejected(client: TestClient) -> None:
    email = _email()
    client.post("/api/auth/register", json=_register_body(email))
    token = _token(client, email)
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    payload["exp"] = payload["iat"] - 10
    expired = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_role_dependencies_reject_the_other_role(client: TestClient, db_session: Session) -> None:
    customer_email = _email()
    admin_email = _email()
    client.post("/api/auth/register", json=_register_body(customer_email))
    client.post("/api/auth/register", json=_register_body(admin_email, full_name="Admin User"))
    admin = db_session.scalar(select(User).where(User.email == admin_email))
    assert admin is not None
    admin.role = UserRole.admin
    db_session.commit()

    customer_headers = {"Authorization": f"Bearer {_token(client, customer_email)}"}
    admin_headers = {"Authorization": f"Bearer {_token(client, admin_email)}"}

    assert client.get("/api/test-auth/customer", headers=customer_headers).status_code == 200
    assert client.get("/api/test-auth/admin", headers=customer_headers).status_code == 403
    assert client.get("/api/test-auth/admin", headers=admin_headers).status_code == 200
    assert client.get("/api/test-auth/customer", headers=admin_headers).status_code == 403

    me = client.get("/api/auth/me", headers=admin_headers)
    assert me.status_code == 200
    assert me.json()["role"] == "ADMIN"
