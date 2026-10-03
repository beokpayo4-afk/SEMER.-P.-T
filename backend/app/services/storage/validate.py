import re

from app.core.exceptions import APIError

FOLDERS = ("products", "categories", "travel", "events")
MAX_FILENAME_LENGTH = 120
FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,80}\.(jpg|jpeg|png|webp)$")
STORED_URL = re.compile(r"^/uploads/(products|categories|travel|events)/[0-9a-f]{32}\.(jpg|png|webp)$")
STORED_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")
MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

EXTENSION_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
CANONICAL_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
ACCEPTED_CONTENT_TYPES = set(CANONICAL_EXTENSION) | {"", "application/octet-stream"}


def clean_image_reference(value: str) -> str:
    cleaned = value.strip()
    if STORED_URL.fullmatch(cleaned):
        return cleaned
    if cleaned.startswith(("https://", "http://")) and " " not in cleaned and "\\" not in cleaned:
        return cleaned
    raise ValueError("Image URL must be an uploaded image or an http(s) URL")


def validate_folder(folder: str) -> str:
    if folder not in FOLDERS:
        raise APIError(status_code=404, detail="Upload folder not found")
    return folder


def validate_filename(filename: str) -> str:
    if not filename or "\x00" in filename or len(filename) > MAX_FILENAME_LENGTH:
        raise APIError(status_code=422, detail="Filename is not allowed")
    if filename != filename.strip() or "/" in filename or "\\" in filename or ".." in filename:
        raise APIError(status_code=422, detail="Filename is not allowed")
    if not FILENAME_PATTERN.fullmatch(filename):
        raise APIError(status_code=422, detail="Use a jpg, png, or webp file with a single extension")
    return filename.rsplit(".", 1)[1].lower()


def validate_image(content: bytes, extension: str, content_type: str, max_bytes: int) -> tuple[str, str]:
    if not content:
        raise APIError(status_code=422, detail="Image file is empty")
    if len(content) > max_bytes:
        raise APIError(status_code=413, detail="Image is larger than the allowed size")
    detected = _detect_type(content)
    if detected is None:
        raise APIError(status_code=422, detail="File is not a jpeg, png, or webp image")
    declared = content_type.split(";", 1)[0].strip().lower()
    if declared not in ACCEPTED_CONTENT_TYPES:
        raise APIError(status_code=422, detail="File type is not allowed")
    if declared in CANONICAL_EXTENSION and declared != detected:
        raise APIError(status_code=422, detail="File contents do not match the declared type")
    suffix = f".{extension}"
    if EXTENSION_TYPES.get(suffix) != detected:
        raise APIError(status_code=422, detail="File extension does not match the image")
    return CANONICAL_EXTENSION[detected], detected


def _detect_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None
