"""POST /parse-image limits (issues #61, #68): format by magic bytes (415), 8 MB and 25 MP (413),
undecodable (422), EXIF rotation and the 2400 px downscale. The route runs with the FakeProvider."""

from __future__ import annotations

import io
import struct
import zlib

import pytest
from PIL import Image

from smartcart_api.main import app
from smartcart_api.ocr import image as imagemod
from smartcart_api.ocr.image import MAX_BYTES, ImageError, image_hash, prepare, sniff
from smartcart_api.ocr.providers import FakeProvider, png_with_text
from smartcart_api.routes.image import MAX_BODY, get_provider

CONSENT = {"X-Image-Consent": "1"}


@pytest.fixture
def fake():
    provider = FakeProvider()
    app.dependency_overrides[get_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_provider, None)


def send(client, data: bytes, content_type: str = "image/png", kind: str = "list"):
    return client.post(
        "/parse-image", data={"kind": kind}, files={"image": ("x", data, content_type)}, headers=CONSENT
    )


def jpeg(size=(64, 48), exif_orientation: int | None = None) -> bytes:
    buf = io.BytesIO()
    im = Image.new("RGB", size, "white")
    kwargs = {}
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        kwargs["exif"] = exif
    im.save(buf, "JPEG", **kwargs)
    return buf.getvalue()


# --- formats ----------------------------------------------------------------------------------


def test_sniff_by_magic_bytes() -> None:
    webp = io.BytesIO()
    Image.new("RGB", (8, 8)).save(webp, "WEBP")
    assert sniff(jpeg()) == "jpeg"
    assert sniff(png_with_text([])) == "png"
    assert sniff(webp.getvalue()) == "webp"
    assert sniff(b"GIF89a....") is None
    assert sniff(b"%PDF-1.7") is None
    assert sniff(b"RIFF\x00\x00\x00\x00WAVE") is None
    assert sniff(b"") is None


@pytest.mark.db
@pytest.mark.parametrize(
    "payload", [b"GIF89a" + b"\x00" * 64, b"%PDF-1.7\n" + b"x" * 64, b"<html>hi</html>", b"MZ\x90\x00" + b"\x00" * 64]
)
def test_other_formats_are_415_whatever_the_client_says(client, fake, payload) -> None:
    r = send(client, payload, content_type="image/jpeg")
    assert r.status_code == 415
    assert fake.calls == 0


@pytest.mark.db
def test_the_client_content_type_is_not_trusted_either_way(client, fake) -> None:
    assert send(client, jpeg(), content_type="text/plain").status_code == 200
    assert send(client, jpeg(), content_type="application/octet-stream").status_code == 200


@pytest.mark.db
def test_webp_is_accepted(client, fake) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buf, "WEBP")
    assert send(client, buf.getvalue(), "image/webp").status_code == 200


@pytest.mark.db
def test_a_corrupt_image_with_a_valid_signature_is_422(client, fake) -> None:
    assert send(client, b"\x89PNG\r\n\x1a\n" + b"garbage" * 20).status_code == 422
    assert send(client, jpeg()[:40]).status_code == 422
    assert send(client, b"").status_code == 422
    assert fake.calls == 0


# --- sizes ------------------------------------------------------------------------------------


@pytest.mark.db
def test_an_image_over_8_mb_is_413(client, fake) -> None:
    payload = b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_BYTES  # a signature is enough to reach the size check
    r = send(client, payload)
    assert r.status_code == 413
    assert fake.calls == 0


@pytest.mark.db
def test_a_much_larger_body_is_cut_off_by_content_length(client, fake) -> None:
    r = send(client, b"\xff\xd8\xff" + b"\x00" * (MAX_BODY + 1024))
    assert r.status_code == 413


@pytest.mark.db
def test_a_chunked_body_without_content_length_is_cut_off_while_streaming(client, fake) -> None:
    boundary = "sc-boundary"
    head = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"kind\"\r\n\r\nlist\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"a.jpg\"\r\n"
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode()
    sent = 0

    def body():
        nonlocal sent
        yield head + b"\xff\xd8\xff"
        for _ in range(40):  # 40 MB offered
            sent += 1
            yield b"\x00" * (1024 * 1024)

    r = client.post(
        "/parse-image",
        content=body(),
        headers={**CONSENT, "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    assert r.status_code == 413
    assert fake.calls == 0


def png_header(width: int, height: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00")) + chunk(b"IEND", b"")


@pytest.mark.db
@pytest.mark.parametrize("size", [(5100, 5000), (8000, 4000), (60000, 60000)])
def test_more_than_25_megapixels_is_413_before_any_pixel_is_decoded(client, fake, size) -> None:
    r = send(client, png_header(*size))
    assert r.status_code == 413
    assert "25 megapixels" in r.json()["detail"]
    assert fake.calls == 0


@pytest.mark.db
def test_a_24_megapixel_photo_is_accepted_and_downscaled(client, fake) -> None:
    seen: list[tuple[int, int]] = []
    original = fake.read

    def spy(image, kind):
        seen.append(image.size)
        return original(image, kind)

    fake.read = spy  # type: ignore[method-assign]
    big = Image.new("RGB", (6000, 4000), "white")
    r = send(client, png_with_text(["x"], big))
    assert r.status_code == 200
    assert seen == [(2400, 1600)]


# --- decode, rotate, downscale (no HTTP) ------------------------------------------------------


def test_exif_orientation_is_applied() -> None:
    # stored 300 x 100 with orientation 6 (rotate 90 clockwise to display) -> 100 x 300
    assert prepare(jpeg((300, 100), exif_orientation=6)).size == (100, 300)
    assert prepare(jpeg((300, 100), exif_orientation=1)).size == (300, 100)
    assert prepare(jpeg((300, 100), exif_orientation=3)).size == (300, 100)


def test_the_long_side_is_at_most_2400() -> None:
    assert prepare(png_with_text([], Image.new("RGB", (3000, 1000)))).size == (2400, 800)
    assert prepare(png_with_text([], Image.new("RGB", (900, 3600)))).size == (600, 2400)
    assert prepare(png_with_text([], Image.new("RGB", (800, 600)))).size == (800, 600)  # never upscaled


def test_transparency_is_flattened_on_white_and_mode_is_rgb() -> None:
    buf = io.BytesIO()
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(buf, "PNG")
    out = prepare(buf.getvalue())
    assert out.mode == "RGB" and out.getpixel((5, 5)) == (255, 255, 255)
    pal = io.BytesIO()
    Image.new("P", (10, 10)).save(pal, "PNG")
    assert prepare(pal.getvalue()).mode == "RGB"


def test_errors_carry_the_http_status() -> None:
    with pytest.raises(ImageError) as exc:
        prepare(b"hello")
    assert exc.value.status == 415
    with pytest.raises(ImageError) as exc:
        prepare(b"\xff\xd8\xff" + b"\x00" * (MAX_BYTES + 1))
    assert exc.value.status == 413


def test_image_hash_is_stable_and_pixel_based() -> None:
    a, b = Image.new("RGB", (4, 4), "white"), Image.new("RGB", (4, 4), "white")
    assert image_hash(a) == image_hash(b)
    b.putpixel((0, 0), (1, 2, 3))
    assert image_hash(a) != image_hash(b)


def test_limits_are_the_documented_ones() -> None:
    assert imagemod.MAX_BYTES == 8 * 1024 * 1024
    assert imagemod.MAX_PIXELS == 25_000_000
    assert imagemod.MAX_LONG_SIDE == 2400
