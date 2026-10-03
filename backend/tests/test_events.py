import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.identity import User


def _customer(client: TestClient) -> dict[str, str]:
    email = f"event-{uuid.uuid4().hex}@example.com"
    created = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password1", "full_name": "Host"},
    )
    assert created.status_code == 201
    return {"Authorization": f"Bearer {created.json()['access_token']}"}


def _admin(client: TestClient, db_session: Session) -> dict[str, str]:
    email = f"event-admin-{uuid.uuid4().hex}@example.com"
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


def _service(slug: str, *, status: str = "active", category: str = "wedding", featured: bool = False) -> dict[str, object]:
    return {
        "title": "Garden wedding",
        "slug": slug,
        "category": category,
        "description": "A daytime wedding planned around the garden and the guest flow.",
        "services": "Timeline, vendor coordination, and a day-of lead.",
        "images": [{"url": "https://example.com/wedding.jpg", "alt_text": "Garden", "sort_order": 0}],
        "status": status,
        "featured": featured,
    }


def test_services_are_public_when_active_and_admin_manages_them(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    customer = _customer(client)
    slug = f"garden-{uuid.uuid4().hex[:8]}"
    denied = client.post("/api/events", json=_service(slug))
    assert denied.status_code == 401
    forbidden = client.post("/api/events", json=_service(slug), headers=customer)
    assert forbidden.status_code == 403

    created = client.post("/api/events", json=_service(slug, status="draft"), headers=admin)
    assert created.status_code == 201
    service = created.json()
    assert service["category"] == "wedding"
    assert service["images"][0]["url"] == "https://example.com/wedding.jpg"

    hidden = client.get("/api/events", headers={"Authorization": "Bearer not-a-token"})
    assert hidden.status_code == 200
    assert all(item["id"] != service["id"] for item in hidden.json()["items"])
    assert client.get(f"/api/events/{service['id']}").status_code == 404

    published = client.put("/api/events/" + service["id"], json=_service(slug, featured=True), headers=admin)
    assert published.status_code == 200
    listed = client.get("/api/events", params={"category": "wedding", "featured": True})
    assert any(item["id"] == service["id"] for item in listed.json()["items"])
    detail = client.get(f"/api/events/{service['id']}")
    assert detail.status_code == 200
    assert detail.json()["services"].startswith("Timeline")

    duplicate = client.post("/api/events", json=_service(slug, category="decoration"), headers=admin)
    assert duplicate.status_code == 409

    removed = client.delete(f"/api/events/{service['id']}", headers=admin)
    assert removed.status_code == 204
    assert client.get(f"/api/events/{service['id']}").status_code == 404


def test_event_enquiry_submission_and_admin_notes(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    buyer = _customer(client)
    slug = f"party-{uuid.uuid4().hex[:8]}"
    created = client.post("/api/events", json=_service(slug, category="private_party"), headers=admin)
    assert created.status_code == 201
    service_id = created.json()["id"]
    event_date = (date.today() + timedelta(days=40)).isoformat()
    body = {
        "service_id": service_id,
        "name": "Meera Shah",
        "email": "meera@example.com",
        "phone": "+91 98450 22222",
        "event_type": "private_party",
        "event_date": event_date,
        "location": "Pune",
        "expected_guests": 80,
        "budget": 25000000,
        "requirements": "A seated dinner and a small stage.",
        "message": "We already have the venue for the evening.",
        "status": "contacted",
        "internal_notes": "Call the venue first.",
    }
    forged = client.post("/api/events/enquiries", json=body)
    assert forged.status_code == 422

    submitted = client.post(
        "/api/events/enquiries",
        json={key: value for key, value in body.items() if key not in {"status", "internal_notes"}},
        headers=buyer,
    )
    assert submitted.status_code == 201
    enquiry = submitted.json()
    assert enquiry["status"] == "new"
    assert enquiry["budget"] == 25000000
    assert enquiry["expected_guests"] == 80
    assert enquiry["phone"] == "+919845022222"
    assert enquiry["service_id"] == service_id
    assert "internal_notes" not in enquiry

    assert client.get("/api/events/enquiries", headers=buyer).status_code == 403
    assert client.get("/api/events/enquiries").status_code == 401

    listed = client.get("/api/events/enquiries", headers=admin)
    assert listed.status_code == 200
    assert any(item["id"] == enquiry["id"] for item in listed.json()["items"])

    noted = client.patch(
        f"/api/events/enquiries/{enquiry['id']}",
        json={"internal_notes": "Venue confirmed for the garden."},
        headers=admin,
    )
    assert noted.status_code == 200
    assert noted.json()["status"] == "new"
    assert noted.json()["internal_notes"] == "Venue confirmed for the garden."

    updated = client.patch(
        f"/api/events/enquiries/{enquiry['id']}",
        json={"status": "contacted"},
        headers=admin,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "contacted"
    assert updated.json()["internal_notes"] == "Venue confirmed for the garden."

    past = client.post(
        "/api/events/enquiries",
        json={
            **{key: value for key, value in body.items() if key not in {"status", "internal_notes"}},
            "event_date": "2020-01-01",
        },
    )
    assert past.status_code == 422

    deleted = client.delete(f"/api/events/enquiries/{enquiry['id']}", headers=admin)
    assert deleted.status_code == 204
    assert client.get(f"/api/events/enquiries/{enquiry['id']}", headers=admin).status_code == 404
