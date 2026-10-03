from typing import Protocol


class ImageStore(Protocol):
    def save(self, folder: str, content: bytes, extension: str, content_type: str) -> str:
        """Store image bytes and return the public URL or path."""

    def delete(self, url: str) -> None:
        """Remove a previously stored image. Missing files are ignored."""
