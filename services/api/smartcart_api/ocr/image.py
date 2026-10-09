"""Validate and decode an uploaded photo, in memory only (decision D11).

Nothing here touches the disk: the bytes come from the request, Pillow decodes from ``BytesIO``,
and the result is a downscaled RGB image. The caller drops every reference before it answers.
"""

from __future__ import annotations

import hashlib
import io
from typing import Literal

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 25_000_000
MAX_LONG_SIDE = 2400

Format = Literal["jpeg", "png", "webp"]
MEDIA_TYPES: dict[str, str] = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


class ImageError(Exception):
    """A refusal with the HTTP status the route should answer."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def sniff(data: bytes) -> Format | None:
    """The format by magic bytes. The client's content type and file name are never trusted."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def prepare(data: bytes) -> Image.Image:
    """Bytes to an upright RGB image of at most MAX_LONG_SIDE px; raises ImageError."""
    if not data:
        raise ImageError(422, "the image is empty")
    if len(data) > MAX_BYTES:
        raise ImageError(413, "the image is larger than 8 MB")
    if sniff(data) is None:
        raise ImageError(415, "only JPEG, PNG and WebP images are accepted")
    try:
        with Image.open(io.BytesIO(data)) as opened:
            width, height = opened.size  # from the header, before any pixel is decoded
            if width * height > MAX_PIXELS:
                raise ImageError(413, "the image has more than 25 megapixels")
            opened.load()
            info = {k: v for k, v in opened.info.items() if isinstance(k, str)}
            image = _flatten(ImageOps.exif_transpose(opened))
    except ImageError:
        raise
    except Image.DecompressionBombError as exc:
        raise ImageError(413, "the image has more than 25 megapixels") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError) as exc:
        raise ImageError(422, "the image could not be decoded") from exc
    image.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE), Image.Resampling.LANCZOS)
    # Text chunks (the fake provider reads the PNG chunk ``sc-ocr``) do not always survive the
    # transforms above; carry the original's info across.
    image.info.update(info)
    return image


def _flatten(image: Image.Image) -> Image.Image:
    """RGB, with transparency composited on white (a transparent PNG would turn black)."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def image_hash(image: Image.Image) -> str:
    """Stable hash of the pixels a provider sees (the fake provider's registry key)."""
    h = hashlib.sha256()
    h.update(f"{image.mode}:{image.size[0]}x{image.size[1]}".encode())
    h.update(image.tobytes())
    return h.hexdigest()


def to_bytes(image: Image.Image, fmt: Literal["JPEG", "PNG"] = "JPEG") -> bytes:
    """Encode in memory (for the vision API and Tesseract's stdin)."""
    buf = io.BytesIO()
    if fmt == "JPEG":
        image.convert("RGB").save(buf, "JPEG", quality=88)
    else:
        image.save(buf, "PNG")
    return buf.getvalue()
