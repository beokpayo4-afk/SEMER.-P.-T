import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import APIError
from app.models.catalog import Category
from app.models.enums import UserRole
from app.models.identity import User
from app.services.storage.s3 import S3ImageStore

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01"
    b"\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _admin(client: TestClient, db_session: Session) -> dict[str, str]:
    email = f"upload-admin-{uuid.uuid4().hex}@example.com"
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


def test_upload_stores_a_file_and_returns_a_url(client: TestClient, db_session: Session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "image_upload_dir", str(tmp_path))
    admin = _admin(client, db_session)
    uploaded = client.post(
        "/api/admin/uploads/categories",
        files={"file": ("photo.png", PNG, "image/png")},
        headers=admin,
    )
    assert uploaded.status_code == 201
    url = uploaded.json()["url"]
    assert url.startswith("/uploads/categories/")
    assert url.endswith(".png")
    stored = tmp_path / "categories" / url.rsplit("/", 1)[1]
    assert stored.is_file()
    assert stored.read_bytes() == PNG

    served = client.get(url)
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("image/png")
    assert served.headers["x-content-type-options"] == "nosniff"
    assert served.content == PNG

    created = client.post(
        "/api/categories",
        json={"name": "Skincare", "slug": f"skin-{uuid.uuid4().hex[:8]}", "image_url": url, "is_active": True},
        headers=admin,
    )
    assert created.status_code == 201
    assert created.json()["image_url"] == url
    db_session.expire_all()
    category = db_session.get(Category, uuid.UUID(created.json()["id"]))
    assert category is not None
    assert category.image_url == url


def test_upload_rejects_unsafe_files(client: TestClient, db_session: Session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "image_upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "image_max_bytes", 32)
    admin = _admin(client, db_session)
    customer = client.post(
        "/api/auth/register",
        json={"email": f"upload-{uuid.uuid4().hex}@example.com", "password": "Password1", "full_name": "Guest"},
    ).json()
    buyer = {"Authorization": f"Bearer {customer['access_token']}"}

    assert client.post("/api/admin/uploads/products", files={"file": ("photo.png", PNG, "image/png")}).status_code == 401
    assert client.post(
        "/api/admin/uploads/products",
        files={"file": ("photo.png", PNG, "image/png")},
        headers=buyer,
    ).status_code == 403
    assert client.post(
        "/api/admin/uploads/products",
        files={"file": ("page.jpg", b"<html>not an image</html>", "image/jpeg")},
        headers=admin,
    ).status_code == 422
    assert client.post(
        "/api/admin/uploads/products",
        files={"file": ("../secret.png", PNG, "image/png")},
        headers=admin,
    ).status_code == 422
    assert client.post(
        "/api/admin/uploads/products",
        files={"file": ("shell.php.png", PNG, "image/png")},
        headers=admin,
    ).status_code == 422
    assert client.post(
        "/api/admin/uploads/products",
        files={"file": ("photo.png", PNG, "image/png")},
        headers=admin,
    ).status_code == 413
    assert client.get("/uploads/products/not-an-image.html").status_code == 404
    assert client.get("/uploads/secrets/" + "a" * 32 + ".png").status_code == 404


def test_s3_store_fails_closed_without_a_client() -> None:
    store = S3ImageStore(
        bucket="",
        endpoint_url="",
        region="",
        access_key="",
        secret_key="",
        public_base_url="",
    )
    try:
        store.save("products", PNG, ".png", "image/png")
    except APIError as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("S3 storage should not accept an upload before it is connected")
