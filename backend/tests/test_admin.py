import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.identity import User


def _customer(client: TestClient) -> dict[str, str]:
    email = f"admin-customer-{uuid.uuid4().hex}@example.com"
    created = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password1", "full_name": "Customer"},
    )
    assert created.status_code == 201
    return {"Authorization": f"Bearer {created.json()['access_token']}"}


def _admin(client: TestClient, db_session: Session) -> dict[str, str]:
    email = f"admin-user-{uuid.uuid4().hex}@example.com"
    created = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password1", "full_name": "Admin"},
    )
    assert created.status_code == 201
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = UserRole.admin
    db_session.commit()
    token = client.post("/api/auth/login", json={"email": email, "password": "Password1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_routes_reject_customers_and_guests(client: TestClient) -> None:
    customer = _customer(client)
    assert client.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/admin/dashboard", headers=customer).status_code == 403
    assert client.get("/api/admin/customers", headers=customer).status_code == 403
    assert client.get("/api/admin/payments", headers=customer).status_code == 403
    assert client.get("/api/admin/settings", headers=customer).status_code == 403
    missing = uuid.uuid4()
    assert client.patch(f"/api/admin/orders/{missing}", json={"status": "SHIPPED"}, headers=customer).status_code == 403
    assert client.patch(f"/api/admin/products/{missing}/stock", json={"stock_quantity": 1}, headers=customer).status_code == 403


def test_admin_dashboard_coupons_and_settings(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    dashboard = client.get("/api/admin/dashboard", headers=admin)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["total_orders"] >= 0
    assert body["total_sales"] >= 0
    assert len(body["months"]) == 6
    assert {"month", "sales", "orders"} <= set(body["months"][0])

    settings = client.get("/api/admin/settings", headers=admin)
    assert settings.status_code == 200
    assert set(settings.json()) == {
        "store_name",
        "currency",
        "payment_provider",
        "low_stock_threshold",
        "environment",
    }
    assert settings.json()["low_stock_threshold"] == 5

    code = f"SAVE{uuid.uuid4().hex[:6].upper()}"
    created = client.post(
        "/api/admin/coupons",
        json={"code": code, "discount_type": "percent", "discount_value": 10, "is_active": True},
        headers=admin,
    )
    assert created.status_code == 201
    coupon = created.json()
    assert coupon["code"] == code
    duplicate = client.post(
        "/api/admin/coupons",
        json={"code": code.lower(), "discount_type": "percent", "discount_value": 10},
        headers=admin,
    )
    assert duplicate.status_code == 409
    removed = client.delete(f"/api/admin/coupons/{coupon['id']}", headers=admin)
    assert removed.status_code == 204

    missing = uuid.uuid4()
    assert client.patch(f"/api/admin/orders/{missing}", json={"status": "DELIVERED"}, headers=admin).status_code == 404
    assert client.patch(
        f"/api/admin/products/{missing}/stock",
        json={"stock_quantity": 4},
        headers=admin,
    ).status_code == 404
