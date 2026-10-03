import uuid
from pathlib import Path

from app.core.exceptions import APIError
from app.services.storage.validate import FOLDERS, STORED_NAME


class LocalImageStore:
    def __init__(self, root: Path, public_prefix: str) -> None:
        self.root = root
        self.public_prefix = "/" + public_prefix.strip("/")

    def save(self, folder: str, content: bytes, extension: str, content_type: str) -> str:
        if folder not in FOLDERS or extension not in {".jpg", ".png", ".webp"}:
            raise APIError(status_code=422, detail="Image could not be stored")
        directory = (self.root / folder).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}{extension}"
        destination = (directory / name).resolve()
        if not destination.is_relative_to(directory):
            raise APIError(status_code=422, detail="Image could not be stored")
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.write_bytes(content)
        temporary.replace(destination)
        return f"{self.public_prefix}/{folder}/{name}"

    def delete(self, url: str) -> None:
        relative = self._relative(url)
        if relative is None:
            return
        path = (self.root / relative).resolve()
        folder = (self.root / relative.split("/", 1)[0]).resolve()
        if not path.is_relative_to(folder) or not path.is_file():
            return
        path.unlink()

    def _relative(self, url: str) -> str | None:
        prefix = self.public_prefix + "/"
        if not url.startswith(prefix):
            return None
        relative = url[len(prefix) :]
        parts = relative.split("/")
        if len(parts) != 2 or parts[0] not in FOLDERS or not STORED_NAME.fullmatch(parts[1]):
            return None
        return relative
