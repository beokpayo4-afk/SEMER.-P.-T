import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.catalog import Product
from tests.test_orders import _admin, _checkout, _customer, _product


def test_guests_and_customers_cannot_use_protected_apis(client: TestClient) -> None:
    customer, _customer_id, _email = _customer(client)
    missing = str(uuid.uuid4())

    assert client.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/admin/customers", headers=customer).status_code == 403
    assert client.post("/api/products", json={}).status_code == 401
    assert client.post("/api/products", json={}, headers=customer).status_code == 403
    assert client.post("/api/categories", json={}).status_code == 401
    assert client.post("/api/travel", json={}).status_code == 401
    assert client.post("/api/events", json={}, headers=customer).status_code == 403
    assert client.get("/api/cart").status_code == 401
    assert client.get("/api/cart", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    assert client.post("/api/orders", json={}).status_code == 401
    assert client.post("/api/payments/create", json={}).status_code == 401
    assert client.get("/api/travel/enquiries").status_code == 401
    assert client.get("/api/travel/enquiries", headers=customer).status_code == 403
    assert client.get("/api/events/enquiries").status_code == 401
    assert client.get("/api/events/enquiries", headers=customer).status_code == 403
    assert client.get(f"/api/orders/{missing}").status_code == 401
    assert client.get("/api/orders/not-an-id", headers=customer).status_code == 422
    assert client.get(f"/api/orders/{missing}", headers=customer).status_code == 404


def test_catalog_cart_checkout_and_payment_reject_invalid_requests(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = _admin(client, db_session)
    buyer, _buyer_id, email = _customer(client)
    category = client.post(
        "/api/categories",
        json={"name": "Care", "slug": f"care-{uuid.uuid4().hex[:8]}", "is_active": True},
        headers=admin,
    )
    assert category.status_code == 201
    category_id = category.json()["id"]
    product_body = {
        "name": "Rose Serum",
        "slug": f"rose-{uuid.uuid4().hex[:8]}",
        "description": "Daily serum",
        "price": 150000,
        "sku": f"SKU-{uuid.uuid4().hex[:8]}",
        "stock_quantity": 1,
        "category_id": category_id,
        "status": "active",
        "images": [],
        "variants": [],
    }

    assert client.get("/api/products/not-a-product").status_code == 422
    assert client.get(f"/api/products/{uuid.uuid4()}").status_code == 404
    negative = dict(product_body, price=-1, slug=f"bad-{uuid.uuid4().hex[:8]}", sku=f"SKU-{uuid.uuid4().hex[:6]}")
    assert client.post("/api/products", json=negative, headers=admin).status_code == 422
    overpriced = dict(product_body, sale_price=200000, slug=f"sale-{uuid.uuid4().hex[:8]}", sku=f"SKU-{uuid.uuid4().hex[:6]}")
    assert client.post("/api/products", json=overpriced, headers=admin).status_code == 422

    created = client.post("/api/products", json=product_body, headers=admin)
    assert created.status_code == 201
    product_id = created.json()["id"]

    assert client.post(
        "/api/cart/items",
        json={"product_id": product_id, "quantity": 0},
        headers=buyer,
    ).status_code == 422
    assert client.post(
        "/api/cart/items",
        json={"product_id": str(uuid.uuid4()), "quantity": 1},
        headers=buyer,
    ).status_code == 404
    blocked = client.post(
        "/api/cart/items",
        json={"product_id": product_id, "quantity": 2},
        headers=buyer,
    )
    assert blocked.status_code == 409

    added = client.post("/api/cart/items", json={"product_id": product_id, "quantity": 1}, headers=buyer)
    assert added.status_code == 201
    stored = db_session.get(Product, uuid.UUID(product_id))
    assert stored is not None
    stored.stock_quantity = 0
    db_session.commit()
    insufficient = client.post("/api/orders", json=_checkout(email), headers=buyer)
    assert insufficient.status_code == 409

    stored.stock_quantity = 1
    db_session.commit()
    invalid_checkout = _checkout(email)
    invalid_checkout["billing"]["country"] = "India"
    assert client.post("/api/orders", json=invalid_checkout, headers=buyer).status_code == 422

    missing_payment = str(uuid.uuid4())
    assert client.post(
        "/api/payments/verify",
        json={"payment_id": missing_payment},
        headers=buyer,
    ).status_code == 404
    assert client.post(
        "/api/payments/create",
        json={"order_id": missing_payment, "payment_method": "cod"},
        headers=buyer,
    ).status_code == 404
    assert client.post("/api/payments/webhook", json={"status": "PAID"}).status_code == 401


def test_enquiries_reject_invalid_input(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    product = _product(client, admin)
    buyer, _buyer_id, email = _customer(client)
    assert client.post(
        "/api/cart/items",
        json={"product_id": product["id"], "quantity": 1},
        headers=buyer,
    ).status_code == 201
    empty = client.post("/api/orders", json=_checkout(f"other-{uuid.uuid4().hex}@example.com"), headers=buyer)
    assert empty.status_code == 422

    past = (date.today() - timedelta(days=1)).isoformat()
    travel = {
        "name": "Asha Rao",
        "email": "not-an-email",
        "phone": "9845011111",
        "destination": "Goa",
        "travel_date": past,
        "travelers": 2,
        "budget": 100000,
        "message": "A short break",
    }
    assert client.post("/api/travel/enquiries", json=travel).status_code == 422
    travel["email"] = "asha@example.com"
    travel["travelers"] = 0
    assert client.post("/api/travel/enquiries", json=travel).status_code == 422

    event = {
        "name": "Asha Rao",
        "email": "asha@example.com",
        "phone": "9845011111",
        "event_type": "not-a-type",
        "event_date": past,
        "location": "Pune",
        "expected_guests": 0,
        "budget": 100000,
        "requirements": "Dinner",
        "message": "A celebration",
    }
    assert client.post("/api/events/enquiries", json=event).status_code == 422
    event["event_type"] = "wedding"
    event["expected_guests"] = 40
    assert client.post("/api/events/enquiries", json=event).status_code == 422
