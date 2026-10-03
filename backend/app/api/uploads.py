from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel

from app.api.deps import require_admin
from app.core.config import settings
from app.core.exceptions import APIError
from app.models.identity import User
from app.services.storage import get_image_store
from app.services.storage.validate import validate_filename, validate_folder, validate_image

router = APIRouter(dependencies=[Depends(require_admin)])


class UploadResult(BaseModel):
    url: str


@router.post("/{folder}", response_model=UploadResult, status_code=201)
async def upload_image(
    folder: str,
    file: UploadFile,
    _: Annotated[User, Depends(require_admin)],
) -> UploadResult:
    validate_folder(folder)
    extension = validate_filename(file.filename or "")
    content = await _read_limited(file, settings.image_max_bytes)
    stored_extension, content_type = validate_image(
        content,
        extension,
        file.content_type or "",
        settings.image_max_bytes,
    )
    url = get_image_store().save(folder, content, stored_extension, content_type)
    return UploadResult(url=url)


async def _read_limited(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        block = await file.read(64 * 1024)
        if not block:
            break
        total += len(block)
        if total > max_bytes:
            raise APIError(status_code=413, detail="Image is larger than the allowed size")
        chunks.append(block)
    return b"".join(chunks)
