"""Image storage.

Files are written by an ImageStore implementation. PostgreSQL keeps the returned
URL only. IMAGE_STORAGE=local writes under the upload directory. IMAGE_STORAGE=s3
uses the same save/delete contract for an S3-compatible bucket.
"""

from app.core.config import settings
from app.services.storage.local import LocalImageStore
from app.services.storage.s3 import S3ImageStore
from app.services.storage.types import ImageStore

__all__ = ["ImageStore", "get_image_store"]


def get_image_store() -> ImageStore:
    kind = settings.image_storage
    if kind == "local":
        return LocalImageStore(settings.resolved_upload_dir, settings.image_public_prefix)
    if kind == "s3":
        return S3ImageStore(
            bucket=settings.image_s3_bucket,
            endpoint_url=settings.image_s3_endpoint,
            region=settings.image_s3_region,
            access_key=settings.image_s3_access_key,
            secret_key=settings.image_s3_secret_key,
            public_base_url=settings.image_s3_public_base_url,
        )
    raise RuntimeError("IMAGE_STORAGE must be local or s3")
