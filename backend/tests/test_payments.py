import hashlib
import hmac
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.commerce import Payment
from tests.test_orders import _admin, _checkout, _customer, _product


def _signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _place(client: TestClient, db_session: Session) -> tuple[dict[str, str], dict[str, object], Payment]:
    admin = _admin(client, db_session)
    buyer, _buyer_id, email = _customer(client)
    product = _product(client, admin)
    added = client.post("/api/cart/items", json={"product_id": product["id"], "quantity": 2}, headers=buyer)
    assert added.status_code == 201
    placed = client.post("/api/orders", json=_checkout(email), headers=buyer)
    assert placed.status_code == 201
    order = placed.json()
    payment = db_session.scalar(select(Payment).where(Payment.order_id == uuid.UUID(order["id"])))
    assert payment is not None
    return buyer, order, payment


def test_payment_uses_order_total_and_backend_verification(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "webhook-secret"
    monkeypatch.setattr(settings, "payment_webhook_secret", secret)
    buyer, order, payment = _place(client, db_session)
    assert payment.amount_paise == 240000
    assert payment.currency == "INR"
    assert payment.provider == "manual"
    assert payment.transaction_id

    forged = client.post(
        "/api/payments/create",
        json={"order_id": order["id"], "payment_method": "cod", "amount": 1, "card_number": "4242424242424242", "cvv": "123"},
        headers=buyer,
    )
    assert forged.status_code == 422

    created = client.post(
        "/api/payments/create",
        json={"order_id": order["id"], "payment_method": "cod"},
        headers=buyer,
    )
    assert created.status_code == 200
    body = created.json()
    assert body["id"] == str(payment.id)
    assert body["amount"] == 240000
    assert body["currency"] == "INR"
    assert body["provider"] == "manual"
    assert body["status"] == "PENDING"
    assert body["payment_method"] == "cod"
    assert "card_number" not in body

    marked = client.post(
        "/api/payments/verify",
        json={"payment_id": str(payment.id), "status": "PAID", "amount": 1},
        headers=buyer,
    )
    assert marked.status_code == 422

    verified = client.post("/api/payments/verify", json={"payment_id": str(payment.id)}, headers=buyer)
    assert verified.status_code == 200
    assert verified.json()["status"] == "PENDING"
    assert verified.json()["amount"] == 240000

    other, _other_id, _other_email = _customer(client, "Other")
    hidden = client.post(
        "/api/payments/create",
        json={"order_id": order["id"], "payment_method": "cod"},
        headers=other,
    )
    assert hidden.status_code == 404
    hidden_verify = client.post("/api/payments/verify", json={"payment_id": str(payment.id)}, headers=other)
    assert hidden_verify.status_code == 404

    event = json.dumps({"transaction_id": payment.transaction_id, "status": "PAID"}).encode()
    unsigned = client.post("/api/payments/webhook", content=event, headers={"X-Payment-Signature": "nope"})
    assert unsigned.status_code == 401
    db_session.refresh(payment)
    assert payment.status.value == "pending"

    paid = client.post(
        "/api/payments/webhook",
        content=event,
        headers={"X-Payment-Signature": _signature(event, secret), "Content-Type": "application/json"},
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "PAID"
    assert paid.json()["amount"] == 240000
    detail = client.get(f"/api/orders/{order['id']}", headers=buyer)
    assert detail.json()["status"] == "CONFIRMED"
    assert detail.json()["payment_status"] == "PAID"

    sensitive = json.dumps(
        {"transaction_id": payment.transaction_id, "status": "PAID", "upi_pin": "1234"}
    ).encode()
    rejected = client.post(
        "/api/payments/webhook",
        content=sensitive,
        headers={"X-Payment-Signature": _signature(sensitive, secret)},
    )
    assert rejected.status_code == 422

    refund = json.dumps({"transaction_id": payment.transaction_id, "status": "REFUNDED"}).encode()
    refunded = client.post(
        "/api/payments/webhook",
        content=refund,
        headers={"X-Payment-Signature": _signature(refund, secret)},
    )
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "REFUNDED"
    detail = client.get(f"/api/orders/{order['id']}", headers=buyer)
    assert detail.json()["status"] == "REFUNDED"


def test_webhook_requires_configured_secret(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "payment_webhook_secret", "")
    _buyer, _order, payment = _place(client, db_session)
    event = json.dumps({"transaction_id": payment.transaction_id, "status": "PAID"}).encode()
    response = client.post(
        "/api/payments/webhook",
        content=event,
        headers={"X-Payment-Signature": _signature(event, "anything")},
    )
    assert response.status_code == 401
    db_session.refresh(payment)
    assert payment.status.value == "pending"
