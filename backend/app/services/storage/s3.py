import uuid

from app.core.exceptions import APIError
from app.services.storage.validate import FOLDERS


class S3ImageStore:
    """S3-compatible store with the same save/delete contract as local disk.

    The object key is ``{folder}/{uuid}{extension}``. Connecting a client such
    as boto3 belongs in ``_put_object`` and ``_delete_object``; until that
    client is configured, calls fail closed and nothing is written to PostgreSQL.
    """

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        region: str,
        access_key: str,
        secret_key: str,
        public_base_url: str,
    ) -> None:
        self.bucket = bucket.strip()
        self.endpoint_url = endpoint_url.strip()
        self.region = region.strip()
        self.access_key = access_key
        self.secret_key = secret_key
        self.public_base_url = public_base_url.rstrip("/")

    def save(self, folder: str, content: bytes, extension: str, content_type: str) -> str:
        self._require_config()
        if folder not in FOLDERS or extension not in {".jpg", ".png", ".webp"}:
            raise APIError(status_code=422, detail="Image could not be stored")
        key = f"{folder}/{uuid.uuid4().hex}{extension}"
        self._put_object(key, content, content_type)
        return f"{self.public_base_url}/{key}"

    def delete(self, url: str) -> None:
        self._require_config()
        prefix = self.public_base_url + "/"
        if not url.startswith(prefix):
            return
        self._delete_object(url[len(prefix) :])

    def _require_config(self) -> None:
        if not self.bucket or not self.public_base_url or not self.access_key or not self.secret_key:
            raise APIError(status_code=503, detail="S3 image storage is not configured")

    def _put_object(self, key: str, content: bytes, content_type: str) -> None:
        raise APIError(status_code=503, detail="S3 image storage is not connected")

    def _delete_object(self, key: str) -> None:
        raise APIError(status_code=503, detail="S3 image storage is not connected")
