import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.identity import User


def _email() -> str:
    return f"catalog-{uuid.uuid4().hex}@example.com"


def _register(client: TestClient, db_session: Session, *, admin: bool) -> dict[str, str]:
    email = _email()
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password1", "full_name": "Catalog User"},
    )
    assert response.status_code == 201
    if admin:
        user = db_session.scalar(select(User).where(User.email == email))
        assert user is not None
        user.role = UserRole.admin
        db_session.commit()
    token = client.post("/api/auth/login", json={"email": email, "password": "Password1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _category(name: str, slug: str, **extra: object) -> dict[str, object]:
    body: dict[str, object] = {"name": name, "slug": slug, "is_active": True}
    body.update(extra)
    return body


def _product(category_id: str, slug: str, **extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "Rose Serum",
        "slug": slug,
        "description": "Daily serum",
        "price": 150000,
        "sale_price": 120000,
        "sku": f"SKU-{slug}",
        "stock_quantity": 4,
        "category_id": category_id,
        "brand": "SEMER",
        "status": "active",
        "featured": False,
        "images": [{"url": "https://example.com/serum.jpg", "alt_text": "Serum", "sort_order": 1}],
        "variants": [
            {
                "sku": f"VAR-{slug}",
                "name": "30 ml",
                "price": 150000,
                "sale_price": 99000,
                "stock_quantity": 2,
            }
        ],
    }
    body.update(extra)
    return body


def test_category_crud_is_admin_only_and_hides_inactive(client: TestClient, db_session: Session) -> None:
    admin = _register(client, db_session, admin=True)
    customer = _register(client, db_session, admin=False)

    denied = client.post("/api/categories", json=_category("Skincare", "skincare"))
    assert denied.status_code == 401
    forbidden = client.post("/api/categories", json=_category("Skincare", "skincare"), headers=customer)
    assert forbidden.status_code == 403

    created = client.post("/api/categories", json=_category("Skincare", "skincare"), headers=admin)
    assert created.status_code == 201
    category = created.json()
    assert category["slug"] == "skincare"
    category_id = category["id"]

    child = client.post(
        "/api/categories",
        json=_category("Serums", "serums", parent_id=category_id),
        headers=admin,
    )
    assert child.status_code == 201

    listed = client.get("/api/categories")
    assert listed.status_code == 200
    assert {item["slug"] for item in listed.json()} == {"skincare", "serums"}

    fetched = client.get(f"/api/categories/{category_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Skincare"

    missing = client.get(f"/api/categories/{uuid.uuid4()}")
    assert missing.status_code == 404

    renamed = client.put(
        f"/api/categories/{category_id}",
        json=_category("Skin Care", "skin-care", is_active=False),
        headers=admin,
    )
    assert renamed.status_code == 200
    assert renamed.json()["is_active"] is False
    assert client.get(f"/api/categories/{category_id}").status_code == 404
    assert client.get(f"/api/categories/{category_id}", headers=admin).status_code == 200
    public_slugs = {item["slug"] for item in client.get("/api/categories").json()}
    assert "skin-care" not in public_slugs
    admin_slugs = {item["slug"] for item in client.get("/api/categories", headers=admin).json()}
    assert "skin-care" in admin_slugs

    blocked = client.delete(f"/api/categories/{category_id}", headers=admin)
    assert blocked.status_code == 409
    assert client.delete(f"/api/categories/{child.json()['id']}", headers=customer).status_code == 403
    assert client.delete(f"/api/categories/{child.json()['id']}", headers=admin).status_code == 204
    assert client.delete(f"/api/categories/{category_id}", headers=admin).status_code == 204
    assert client.delete(f"/api/categories/{uuid.uuid4()}", headers=admin).status_code == 404


def test_category_rejects_cycles_and_duplicate_slugs(client: TestClient, db_session: Session) -> None:
    admin = _register(client, db_session, admin=True)
    parent = client.post("/api/categories", json=_category("Beauty", "beauty"), headers=admin).json()
    child = client.post(
        "/api/categories",
        json=_category("Hair", "hair", parent_id=parent["id"]),
        headers=admin,
    ).json()

    duplicate = client.post("/api/categories", json=_category("Other", "beauty"), headers=admin)
    assert duplicate.status_code == 409

    own_parent = client.put(
        f"/api/categories/{parent['id']}",
        json=_category("Beauty", "beauty", parent_id=parent["id"]),
        headers=admin,
    )
    assert own_parent.status_code == 422

    cycle = client.put(
        f"/api/categories/{parent['id']}",
        json=_category("Beauty", "beauty", parent_id=child["id"]),
        headers=admin,
    )
    assert cycle.status_code == 422
    assert client.put(
        f"/api/categories/{uuid.uuid4()}",
        json=_category("Missing", "missing"),
        headers=admin,
    ).status_code == 404


def test_product_crud_permissions_and_fields(client: TestClient, db_session: Session) -> None:
    admin = _register(client, db_session, admin=True)
    customer = _register(client, db_session, admin=False)
    category_id = client.post("/api/categories", json=_category("Makeup", "makeup"), headers=admin).json()["id"]
    payload = _product(category_id, "rose-serum")

    assert client.post("/api/products", json=payload).status_code == 401
    assert client.post("/api/products", json=payload, headers=customer).status_code == 403

    created = client.post("/api/products", json=payload, headers=admin)
    assert created.status_code == 201
    product = created.json()
    assert product["name"] == "Rose Serum"
    assert product["price"] == 150000
    assert product["sale_price"] == 120000
    assert product["sku"] == "SKU-rose-serum"
    assert product["stock_quantity"] == 4
    assert product["brand"] == "SEMER"
    assert product["featured"] is False
    assert product["category"]["slug"] == "makeup"
    assert product["images"][0]["url"].endswith("serum.jpg")
    assert product["images"][0]["variant_id"] is None
    assert product["variants"][0]["sku"] == "VAR-rose-serum"
    assert product["variants"][0]["stock_quantity"] == 2
    product_id = product["id"]

    assert client.get(f"/api/products/{product_id}").json()["slug"] == "rose-serum"
    assert client.get(f"/api/products/{uuid.uuid4()}").status_code == 404

    duplicate = client.post("/api/products", json=_product(category_id, "rose-serum"), headers=admin)
    assert duplicate.status_code == 409
    unknown_category = client.post(
        "/api/products",
        json=_product(str(uuid.uuid4()), "missing-category"),
        headers=admin,
    )
    assert unknown_category.status_code == 404

    updated = client.put(
        f"/api/products/{product_id}",
        json=_product(category_id, "rose-serum", name="Rose Serum Plus", price=180000, sale_price=None, featured=True),
        headers=admin,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Rose Serum Plus"
    assert updated.json()["featured"] is True
    assert updated.json()["sale_price"] is None

    assert client.put(f"/api/products/{product_id}", json=payload, headers=customer).status_code == 403
    assert client.delete(f"/api/products/{product_id}", headers=customer).status_code == 403
    assert client.delete(f"/api/products/{product_id}").status_code == 401
    assert client.delete(f"/api/products/{product_id}", headers=admin).status_code == 204
    assert client.get(f"/api/products/{product_id}").status_code == 404
    assert client.delete(f"/api/products/{uuid.uuid4()}", headers=admin).status_code == 404

    blocked = client.post("/api/categories", json=_category("Makeup", "makeup-2"), headers=admin).json()
    kept = client.post("/api/products", json=_product(blocked["id"], "kept-serum"), headers=admin).json()
    assert client.delete(f"/api/categories/{blocked['id']}", headers=admin).status_code == 409
    assert kept["id"]


def test_public_catalog_hides_drafts_and_supports_filters(client: TestClient, db_session: Session) -> None:
    admin = _register(client, db_session, admin=True)
    parent_id = client.post("/api/categories", json=_category("Care", "care"), headers=admin).json()["id"]
    child_id = client.post(
        "/api/categories",
        json=_category("Oils", "oils", parent_id=parent_id),
        headers=admin,
    ).json()["id"]

    draft = _product(parent_id, "draft-oil", status="draft", sku="SKU-draft", stock_quantity=9)
    draft["variants"] = []
    created_draft = client.post("/api/products", json=draft, headers=admin)
    assert created_draft.status_code == 201
    draft_id = created_draft.json()["id"]
    assert client.get(f"/api/products/{draft_id}").status_code == 404
    assert client.get(f"/api/products/{draft_id}", headers=admin).status_code == 200

    cheap = _product(
        child_id,
        "cheap-oil",
        name="Cheap Oil",
        price=5000,
        sale_price=None,
        sku="SKU-cheap",
        stock_quantity=0,
        brand="Budget",
        variants=[{"sku": "VAR-cheap", "name": "Small", "price": 8000, "stock_quantity": 3}],
    )
    mid = _product(
        parent_id,
        "mid-oil",
        name="Mid Oil",
        price=20000,
        sale_price=15000,
        sku="SKU-mid",
        stock_quantity=0,
        brand="SEMER",
        variants=[],
    )
    pricey = _product(
        parent_id,
        "pricey-oil",
        name="Pricey Oil",
        price=90000,
        sale_price=None,
        sku="SKU-pricey",
        stock_quantity=1,
        brand="SEMER",
        variants=[],
    )
    for body in (cheap, mid, pricey):
        assert client.post("/api/products", json=body, headers=admin).status_code == 201

    public = client.get("/api/products")
    assert public.status_code == 200
    public_slugs = {item["slug"] for item in public.json()["items"]}
    assert "draft-oil" not in public_slugs
    assert public.json()["total"] == 3

    by_parent = client.get("/api/products", params={"category": parent_id})
    assert {item["slug"] for item in by_parent.json()["items"]} == {"cheap-oil", "mid-oil", "pricey-oil"}

    by_search = client.get("/api/products", params={"search": "SKU-mid"})
    assert [item["slug"] for item in by_search.json()["items"]] == ["mid-oil"]

    by_price = client.get("/api/products", params={"min_price": 7000, "max_price": 16000})
    assert {item["slug"] for item in by_price.json()["items"]} == {"cheap-oil", "mid-oil"}

    available = client.get("/api/products", params={"available": True})
    assert {item["slug"] for item in available.json()["items"]} == {"cheap-oil", "pricey-oil"}
    unavailable = client.get("/api/products", params={"available": False})
    assert [item["slug"] for item in unavailable.json()["items"]] == ["mid-oil"]

    ordered = client.get("/api/products", params={"sort": "price"})
    assert [item["slug"] for item in ordered.json()["items"]] == ["cheap-oil", "mid-oil", "pricey-oil"]

    page = client.get("/api/products", params={"sort": "name", "page": 2, "page_size": 2})
    assert page.json()["total"] == 3
    assert page.json()["page"] == 2
    assert len(page.json()["items"]) == 1

    assert client.get("/api/products", params={"sort": "nope"}).status_code == 422
    assert client.get("/api/products", params={"category": str(uuid.uuid4())}).status_code == 404
