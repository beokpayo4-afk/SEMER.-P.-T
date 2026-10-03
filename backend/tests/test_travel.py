import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.identity import User


def _customer(client: TestClient) -> dict[str, str]:
    email = f"travel-{uuid.uuid4().hex}@example.com"
    created = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password1", "full_name": "Traveller"},
    )
    assert created.status_code == 201
    return {"Authorization": f"Bearer {created.json()['access_token']}"}


def _admin(client: TestClient, db_session: Session) -> dict[str, str]:
    email = f"travel-admin-{uuid.uuid4().hex}@example.com"
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


def _package(slug: str, *, status: str = "active", category: str = "domestic", featured: bool = False) -> dict[str, object]:
    return {
        "title": "Hills of Coorg",
        "slug": slug,
        "category": category,
        "destination": "Coorg",
        "country": "India",
        "duration": 4,
        "starting_price": 2500000,
        "description": "A short circuit through coffee country.",
        "itinerary": "Day 1 arrival. Day 4 departure.",
        "accommodation": "Estate stay",
        "transportation": "Private car",
        "activities": "Plantation walk",
        "inclusions": "Stay and breakfast",
        "exclusions": "Flights",
        "images": [{"url": "https://example.com/coorg.jpg", "alt_text": "Coorg", "sort_order": 0}],
        "status": status,
        "featured": featured,
    }


def test_packages_are_public_when_active_and_admin_manages_them(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    slug = f"coorg-{uuid.uuid4().hex[:8]}"
    denied = client.post("/api/travel", json=_package(slug))
    assert denied.status_code == 401

    created = client.post("/api/travel", json=_package(slug, status="draft"), headers=admin)
    assert created.status_code == 201
    package = created.json()
    assert package["starting_price"] == 2500000
    assert package["duration"] == 4
    assert package["category"] == "domestic"
    assert package["images"][0]["url"] == "https://example.com/coorg.jpg"

    hidden = client.get("/api/travel", headers={"Authorization": "Bearer not-a-token"})
    assert hidden.status_code == 200
    assert all(item["id"] != package["id"] for item in hidden.json()["items"])
    missing = client.get(f"/api/travel/{package['id']}")
    assert missing.status_code == 404

    published = client.put("/api/travel/" + package["id"], json=_package(slug, featured=True), headers=admin)
    assert published.status_code == 200
    listed = client.get("/api/travel", params={"category": "domestic", "featured": True})
    assert any(item["id"] == package["id"] for item in listed.json()["items"])
    detail = client.get(f"/api/travel/{package['id']}")
    assert detail.status_code == 200
    assert detail.json()["itinerary"].startswith("Day 1")

    duplicate = client.post("/api/travel", json=_package(slug, category="holiday"), headers=admin)
    assert duplicate.status_code == 409

    removed = client.delete(f"/api/travel/{package['id']}", headers=admin)
    assert removed.status_code == 204
    assert client.get(f"/api/travel/{package['id']}").status_code == 404


def test_honeymoon_packages_can_be_published_and_filtered(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    slug = f"honeymoon-{uuid.uuid4().hex[:8]}"
    created = client.post("/api/travel", json=_package(slug, category="honeymoon"), headers=admin)
    assert created.status_code == 201
    package_id = created.json()["id"]
    assert created.json()["category"] == "honeymoon"

    listed = client.get("/api/travel", params={"category": "honeymoon"})
    assert listed.status_code == 200
    assert any(item["id"] == package_id for item in listed.json()["items"])

    other = client.get("/api/travel", params={"category": "domestic"})
    assert all(item["id"] != package_id for item in other.json()["items"])


def test_travel_enquiry_submission_and_admin_management(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    buyer = _customer(client)
    slug = f"jaipur-{uuid.uuid4().hex[:8]}"
    created = client.post("/api/travel", json=_package(slug, category="customized"), headers=admin)
    assert created.status_code == 201
    package_id = created.json()["id"]
    travel_date = (date.today() + timedelta(days=30)).isoformat()
    body = {
        "package_id": package_id,
        "name": "Asha Rao",
        "email": "asha@example.com",
        "phone": "+91 98450 11111",
        "destination": "Jaipur",
        "travel_date": travel_date,
        "travelers": 3,
        "budget": 18000000,
        "message": "We would like a slower pace and one free afternoon.",
        "status": "contacted",
    }
    forged = client.post("/api/travel/enquiries", json=body)
    assert forged.status_code == 422

    submitted = client.post("/api/travel/enquiries", json={key: value for key, value in body.items() if key != "status"}, headers=buyer)
    assert submitted.status_code == 201
    enquiry = submitted.json()
    assert enquiry["status"] == "new"
    assert enquiry["budget"] == 18000000
    assert enquiry["travelers"] == 3
    assert enquiry["phone"] == "+919845011111"
    assert enquiry["package_id"] == package_id

    private = client.get("/api/travel/enquiries", headers=buyer)
    assert private.status_code == 403
    anonymous = client.get("/api/travel/enquiries")
    assert anonymous.status_code == 401

    listed = client.get("/api/travel/enquiries", headers=admin)
    assert listed.status_code == 200
    assert any(item["id"] == enquiry["id"] for item in listed.json()["items"])

    updated = client.patch(
        f"/api/travel/enquiries/{enquiry['id']}",
        json={"status": "contacted"},
        headers=admin,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "contacted"

    past = client.post(
        "/api/travel/enquiries",
        json={**{key: value for key, value in body.items() if key != "status"}, "travel_date": "2020-01-01"},
    )
    assert past.status_code == 422

    deleted = client.delete(f"/api/travel/enquiries/{enquiry['id']}", headers=admin)
    assert deleted.status_code == 204
    assert client.get(f"/api/travel/enquiries/{enquiry['id']}", headers=admin).status_code == 404
