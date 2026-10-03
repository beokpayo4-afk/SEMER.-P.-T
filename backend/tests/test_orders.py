import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import Product, ProductVariant
from app.models.commerce import Cart, Order, Payment
from app.models.enums import CartStatus, OrderStatus, PaymentStatus, UserRole
from app.models.identity import Address, User


def _customer(client: TestClient, name: str = "Buyer") -> tuple[dict[str, str], str, str]:
    email = f"order-{uuid.uuid4().hex}@example.com"
    created = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password1", "full_name": name},
    )
    assert created.status_code == 201
    body = created.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"], email


def _admin(client: TestClient, db_session: Session) -> dict[str, str]:
    email = f"order-admin-{uuid.uuid4().hex}@example.com"
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


def _checkout(email: str, *, same: bool = True) -> dict[str, object]:
    body: dict[str, object] = {
        "customer": {"name": "Asha Rao", "email": email, "phone": "+91 98450 11111"},
        "billing": {
            "address": "12 Lake Road",
            "city": "Pune",
            "state": "Maharashtra",
            "postal_code": "411001",
            "country": "in",
        },
        "shipping_same_as_billing": same,
        "total": 1,
    }
    if not same:
        body["shipping"] = {
            "address": "8 Fort Lane",
            "city": "Jaipur",
            "state": "Rajasthan",
            "postal_code": "302001",
            "country": "IN",
        }
    return body


def test_order_uses_database_prices_stock_and_payment(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    buyer, buyer_id, email = _customer(client)
    product = _product(client, admin, stock=4)
    added = client.post(
        "/api/cart/items",
        json={"product_id": product["id"], "quantity": 2},
        headers=buyer,
    )
    assert added.status_code == 201

    quote = client.get("/api/orders/quote", headers=buyer)
    assert quote.status_code == 200
    assert quote.json()["subtotal"] == 300000
    assert quote.json()["discount"] == 60000
    assert quote.json()["shipping"] == 0
    assert quote.json()["tax"] == 0
    assert quote.json()["total"] == 240000
    assert quote.json()["payment_method"] == "cod"

    placed = client.post("/api/orders", json=_checkout(email), headers=buyer)
    assert placed.status_code == 201
    order = placed.json()
    assert order["status"] == "PENDING"
    assert order["payment_status"] == "PENDING"
    assert order["payment_method"] == "cod"
    assert order["subtotal"] == 300000
    assert order["discount"] == 60000
    assert order["shipping"] == 0
    assert order["total"] == 240000
    assert order["total"] != 1
    assert order["customer_email"] == email
    assert order["customer_phone"] == "+919845011111"
    assert order["billing_address"]["city"] == "Pune"
    assert order["billing_address"]["country"] == "IN"
    assert order["shipping_address"]["city"] == "Pune"
    assert order["items"][0]["quantity"] == 2
    assert order["items"][0]["unit_price"] == 120000
    assert order["items"][0]["list_price"] == 150000
    assert order["items"][0]["line_total"] == 240000

    stored = db_session.get(Product, uuid.UUID(str(product["id"])))
    assert stored is not None
    db_session.refresh(stored)
    assert stored.stock_quantity == 2

    payment = db_session.scalar(select(Payment).where(Payment.order_id == uuid.UUID(order["id"])))
    assert payment is not None
    assert payment.amount_paise == 240000
    assert payment.status == PaymentStatus.pending
    assert payment.payment_method == "cod"

    placement = db_session.get(Order, uuid.UUID(order["id"]))
    assert placement is not None
    placement.status = OrderStatus.processing
    db_session.commit()
    placement.status = OrderStatus.refunded
    db_session.commit()

    converted = db_session.scalar(
        select(Cart).where(Cart.user_id == uuid.UUID(buyer_id), Cart.status == CartStatus.converted)
    )
    assert converted is not None
    assert len(converted.items) == 1
    addresses = db_session.scalar(select(func.count()).select_from(Address).where(Address.user_id == uuid.UUID(buyer_id)))
    assert addresses == 1

    emptied = client.get("/api/cart", headers=buyer)
    assert emptied.status_code == 200
    assert emptied.json()["items"] == []

    own = client.get("/api/orders", headers=buyer)
    assert own.status_code == 200
    assert own.json()["total"] == 1
    assert own.json()["items"][0]["id"] == order["id"]

    detail = client.get(f"/api/orders/{order['id']}", headers=buyer)
    assert detail.status_code == 200
    assert detail.json()["order_number"] == order["order_number"]

    other, _other_id, _other_email = _customer(client, "Other")
    hidden = client.get("/api/orders", headers=other)
    assert hidden.json()["total"] == 0
    missing = client.get(f"/api/orders/{order['id']}", headers=other)
    assert missing.status_code == 404

    visible = client.get("/api/orders", headers=admin)
    assert any(row["id"] == order["id"] for row in visible.json()["items"])
    admin_detail = client.get(f"/api/orders/{order['id']}", headers=admin)
    assert admin_detail.status_code == 200

    anonymous = client.get("/api/orders")
    assert anonymous.status_code == 401


def test_order_rejects_insufficient_stock_and_separate_shipping(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    buyer, buyer_id, email = _customer(client)
    product = _product(client, admin, stock=4, with_variant=True)
    variant_id = product["variants"][0]["id"]  # type: ignore[index]
    added = client.post(
        "/api/cart/items",
        json={"product_id": product["id"], "variant_id": variant_id, "quantity": 2},
        headers=buyer,
    )
    assert added.status_code == 201

    variant = db_session.get(ProductVariant, uuid.UUID(str(variant_id)))
    assert variant is not None
    variant.stock_qty = 1
    db_session.commit()

    blocked = client.post("/api/orders", json=_checkout(email, same=False), headers=buyer)
    assert blocked.status_code == 409
    db_session.refresh(variant)
    assert variant.stock_qty == 1
    assert db_session.scalar(select(func.count()).select_from(Order).where(Order.user_id == uuid.UUID(buyer_id))) == 0

    variant.stock_qty = 4
    db_session.commit()
    placed = client.post("/api/orders", json=_checkout(email, same=False), headers=buyer)
    assert placed.status_code == 201
    body = placed.json()
    assert body["subtotal"] == 300000
    assert body["discount"] == 102000
    assert body["total"] == 198000
    assert body["items"][0]["variant_name"] == "30 ml"
    assert body["items"][0]["unit_price"] == 99000
    assert body["billing_address"]["city"] == "Pune"
    assert body["shipping_address"]["city"] == "Jaipur"
    db_session.refresh(variant)
    assert variant.stock_qty == 2
    address_count = db_session.scalar(
        select(func.count()).select_from(Address).where(Address.user_id == uuid.UUID(buyer_id))
    )
    assert address_count == 2

    mismatch = client.post(
        "/api/orders",
        json=_checkout("someone-else@example.com"),
        headers=buyer,
    )
    assert mismatch.status_code == 422

    empty = client.post("/api/orders", json=_checkout(email), headers=buyer)
    assert empty.status_code == 409
