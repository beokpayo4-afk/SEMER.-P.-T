import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.identity import User


def _customer(client: TestClient, name: str = "Buyer") -> dict[str, str]:
    email = f"cart-{uuid.uuid4().hex}@example.com"
    created = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password1", "full_name": name},
    )
    assert created.status_code == 201
    return {"Authorization": f"Bearer {created.json()['access_token']}"}


def _admin(client: TestClient, db_session: Session) -> dict[str, str]:
    email = f"cart-admin-{uuid.uuid4().hex}@example.com"
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


def _product(
    client: TestClient,
    admin: dict[str, str],
    *,
    stock: int = 4,
    with_variant: bool = False,
) -> dict[str, object]:
    slug = uuid.uuid4().hex[:12]
    category = client.post(
        "/api/categories",
        json={"name": "Care", "slug": f"care-{slug}", "is_active": True},
        headers=admin,
    )
    assert category.status_code == 201
    body: dict[str, object] = {
        "name": "Rose Serum",
        "slug": f"rose-{slug}",
        "description": "Daily serum",
        "price": 150000,
        "sale_price": 120000,
        "sku": f"SKU-{slug}",
        "stock_quantity": stock,
        "category_id": category.json()["id"],
        "status": "active",
        "images": [{"url": "https://example.com/serum.jpg", "alt_text": "Serum", "sort_order": 0}],
        "variants": [],
    }
    if with_variant:
        body["variants"] = [
            {
                "sku": f"VAR-{slug}",
                "name": "30 ml",
                "price": 150000,
                "sale_price": 99000,
                "stock_quantity": stock,
            }
        ]
    created = client.post("/api/products", json=body, headers=admin)
    assert created.status_code == 201
    return created.json()


def test_customer_cart_prices_stock_and_isolation(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    buyer = _customer(client, "Buyer")
    other = _customer(client, "Other")
    product = _product(client, admin, stock=3)

    denied = client.get("/api/cart")
    assert denied.status_code == 401
    admin_cart = client.get("/api/cart", headers=admin)
    assert admin_cart.status_code == 200
    assert admin_cart.json()["items"] == []

    empty = client.get("/api/cart", headers=buyer)
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    assert empty.json()["subtotal"] == 0
    assert empty.json()["discount"] == 0
    assert empty.json()["total"] == 0

    added = client.post(
        "/api/cart/items",
        json={"product_id": product["id"], "quantity": 2},
        headers=buyer,
    )
    assert added.status_code == 201
    item = added.json()["items"][0]
    assert item["quantity"] == 2
    assert item["unit_price"] == 120000
    assert item["list_price"] == 150000
    assert added.json()["subtotal"] == 300000
    assert added.json()["discount"] == 60000
    assert added.json()["total"] == 240000

    over = client.post(
        "/api/cart/items",
        json={"product_id": product["id"], "quantity": 2},
        headers=buyer,
    )
    assert over.status_code == 409
    assert client.get("/api/cart", headers=buyer).json()["items"][0]["quantity"] == 2

    updated = client.put(f"/api/cart/items/{item['id']}", json={"quantity": 1}, headers=buyer)
    assert updated.status_code == 200
    assert updated.json()["total"] == 120000

    hidden = client.put(f"/api/cart/items/{item['id']}", json={"quantity": 1}, headers=other)
    assert hidden.status_code == 404

    removed = client.delete(f"/api/cart/items/{item['id']}", headers=buyer)
    assert removed.status_code == 204
    assert client.get("/api/cart", headers=buyer).json()["items"] == []


def test_variant_lines_and_clear(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    buyer = _customer(client)
    product = _product(client, admin, stock=5, with_variant=True)
    variant_id = product["variants"][0]["id"]

    missing_variant = client.post(
        "/api/cart/items",
        json={"product_id": product["id"], "quantity": 1},
        headers=buyer,
    )
    assert missing_variant.status_code == 422

    added = client.post(
        "/api/cart/items",
        json={"product_id": product["id"], "variant_id": variant_id, "quantity": 2},
        headers=buyer,
    )
    assert added.status_code == 201
    assert added.json()["items"][0]["variant_name"] == "30 ml"
    assert added.json()["items"][0]["unit_price"] == 99000
    assert added.json()["discount"] == 102000
    assert added.json()["total"] == 198000

    cleared = client.delete("/api/cart", headers=buyer)
    assert cleared.status_code == 204
    assert client.get("/api/cart", headers=buyer).json()["items"] == []
