import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.identity import User


def _register(client: TestClient, db_session: Session) -> dict[str, str]:
    email = f"shop-{uuid.uuid4().hex}@example.com"
    created = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password1", "full_name": "Shop User"},
    )
    assert created.status_code == 201
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = UserRole.admin
    db_session.commit()
    token = client.post("/api/auth/login", json={"email": email, "password": "Password1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _customer(client: TestClient) -> dict[str, str]:
    email = f"buyer-{uuid.uuid4().hex}@example.com"
    created = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password1", "full_name": "Buyer"},
    )
    assert created.status_code == 201
    return {"Authorization": f"Bearer {created.json()['access_token']}"}


def _product(client: TestClient, admin: dict[str, str], *, stock: int = 4) -> str:
    slug = uuid.uuid4().hex[:12]
    category = client.post(
        "/api/categories",
        json={"name": "Skincare", "slug": f"skin-{slug}", "is_active": True},
        headers=admin,
    )
    assert category.status_code == 201
    created = client.post(
        "/api/products",
        json={
            "name": "Rose Serum",
            "slug": f"rose-{slug}",
            "description": "Daily serum",
            "price": 150000,
            "sale_price": 120000,
            "sku": f"SKU-{slug}",
            "stock_quantity": stock,
            "category_id": category.json()["id"],
            "status": "active",
            "featured": True,
            "images": [],
            "variants": [],
        },
        headers=admin,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["rating_average"] is None
    assert body["review_count"] == 0
    return str(body["id"])


def test_reviews_update_the_product_rating(client: TestClient, db_session: Session) -> None:
    admin = _register(client, db_session)
    buyer = _customer(client)
    product_id = _product(client, admin)

    denied = client.post(f"/api/products/{product_id}/reviews", json={"rating": 5})
    assert denied.status_code == 401

    created = client.post(
        f"/api/products/{product_id}/reviews",
        json={"rating": 4, "comment": "  Smooth texture  "},
        headers=buyer,
    )
    assert created.status_code == 201
    page = created.json()
    assert page["review_count"] == 1
    assert page["rating_average"] == 4
    assert page["items"][0]["author_name"] == "Buyer"
    assert page["items"][0]["comment"] == "Smooth texture"

    duplicate = client.post(
        f"/api/products/{product_id}/reviews",
        json={"rating": 2},
        headers=buyer,
    )
    assert duplicate.status_code == 409

    listed = client.get(f"/api/products/{product_id}")
    assert listed.json()["review_count"] == 1
    assert listed.json()["rating_average"] == 4

    missing = client.get(f"/api/products/{uuid.uuid4()}/reviews")
    assert missing.status_code == 404


def test_wishlist_adds_and_removes_a_product(client: TestClient, db_session: Session) -> None:
    admin = _register(client, db_session)
    buyer = _customer(client)
    product_id = _product(client, admin)

    denied = client.get("/api/wishlist")
    assert denied.status_code == 401

    added = client.post("/api/wishlist", json={"product_id": product_id}, headers=buyer)
    assert added.status_code == 201
    assert added.json()["product_ids"] == [product_id]

    again = client.post("/api/wishlist", json={"product_id": product_id}, headers=buyer)
    assert again.status_code == 201
    assert again.json()["product_ids"] == [product_id]

    listed = client.get("/api/wishlist", headers=buyer)
    assert listed.json()["product_ids"] == [product_id]

    removed = client.delete(f"/api/wishlist/{product_id}", headers=buyer)
    assert removed.status_code == 204
    assert client.get("/api/wishlist", headers=buyer).json()["product_ids"] == []

    missing = client.post("/api/wishlist", json={"product_id": str(uuid.uuid4())}, headers=buyer)
    assert missing.status_code == 404
