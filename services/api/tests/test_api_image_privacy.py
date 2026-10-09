"""POST /parse-image deletion guarantee (decision D11, issues #61, #68): a request creates no file,
the image bytes and the OCR text reach no log, no reference to the decoded image outlives the
request, and what is stored is a count and an estimate only."""

from __future__ import annotations

import base64
import builtins
import gc
import logging
import os
import tempfile
import weakref

import pytest
from PIL import Image

from smartcart_api.main import app
from smartcart_api.ocr.providers import FakeProvider, OcrError, OcrResult, png_with_text
from smartcart_api.routes.image import get_provider

pytestmark = pytest.mark.db

CONSENT = {"X-Image-Consent": "1"}
SECRET_LINE = "סנטינל-חשאי-QZX93"
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC


@pytest.fixture
def fake():
    provider = FakeProvider()
    app.dependency_overrides[get_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_provider, None)


def noisy_png(lines: list[str], side: int = 1500) -> bytes:
    """A PNG of random pixels: about 6.7 MB, far over the 1 MB where an upload spools to disk."""
    image = Image.frombytes("RGB", (side, side), os.urandom(side * side * 3))
    data = png_with_text(lines, image)
    assert 2 * 1024 * 1024 < len(data) < 8 * 1024 * 1024
    return data


def post(client, data: bytes, kind: str = "list"):
    return client.post(
        "/parse-image",
        data={"kind": kind},
        files={"image": ("p.png", data, "image/png")},
        headers=CONSENT,
    )


@pytest.mark.parametrize("kind", ["list", "receipt"])
def test_a_request_creates_no_file_anywhere(client, fake, monkeypatch, tmp_path, kind) -> None:
    created: list[str] = []

    def forbid(name):
        def inner(*args, **kwargs):
            created.append(name)
            raise AssertionError(f"tempfile.{name} called during /parse-image")

        return inner

    for name in ("TemporaryFile", "NamedTemporaryFile", "mkstemp", "mkdtemp", "TemporaryDirectory"):
        monkeypatch.setattr(tempfile, name, forbid(name))
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    real_open, real_os_open = builtins.open, os.open
    opened_for_write: list[str] = []

    def spy_open(file, mode="r", *args, **kwargs):
        if isinstance(mode, str) and any(c in mode for c in "wax+"):
            opened_for_write.append(str(file))
        return real_open(file, mode, *args, **kwargs)

    def spy_os_open(path, flags, *args, **kwargs):
        if flags & WRITE_FLAGS:
            opened_for_write.append(str(path))
        return real_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(os, "open", spy_os_open)

    lines = ["עגבניות 5.00", "בננות 6.00"] if kind == "receipt" else ["עגבניות", "בננות"]
    r = post(client, noisy_png(lines), kind)
    monkeypatch.undo()

    assert r.status_code == 200, r.text
    assert created == []
    assert opened_for_write == [], opened_for_write
    assert list(tmp_path.iterdir()) == []


def test_no_image_bytes_and_no_ocr_text_reach_the_logs(client, fake, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    data = noisy_png([SECRET_LINE, "עגבניות"])
    r = post(client, data)
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    logged = "\n".join(
        [rec.getMessage() for rec in caplog.records] + [repr(rec.args) for rec in caplog.records]
    )
    assert SECRET_LINE not in logged
    assert "QZX93" not in logged
    for probe in (data[:64], data[1000:1064], data[-64:]):
        assert base64.b64encode(probe).decode() not in logged
        assert probe.hex() not in logged
        assert repr(probe) not in logged
    assert any(rec.name == "smartcart.ocr" for rec in caplog.records)  # counts are logged
    ours = [rec for rec in caplog.records if rec.name == "smartcart.ocr"]
    assert all("lines=" in rec.getMessage() for rec in ours)


def test_the_response_does_not_echo_the_raw_text_of_a_failed_read(client, caplog) -> None:
    class Leaky(FakeProvider):
        def read(self, image, kind):
            raise OcrError(SECRET_LINE)

    app.dependency_overrides[get_provider] = lambda: Leaky()
    caplog.set_level(logging.DEBUG)
    try:
        r = post(client, png_with_text([SECRET_LINE]))
    finally:
        app.dependency_overrides.pop(get_provider, None)
    assert r.status_code == 502
    assert SECRET_LINE not in r.text
    assert SECRET_LINE not in caplog.text


def test_the_decoded_image_is_released_before_the_response(client) -> None:
    refs: list[weakref.ref] = []

    class Watching(FakeProvider):
        def read(self, image, kind):
            refs.append(weakref.ref(image))
            return OcrResult(["עגבניות"], "fake", 0.0)

    app.dependency_overrides[get_provider] = lambda: Watching()
    try:
        r = post(client, png_with_text(["x"], Image.new("RGB", (600, 600), "white")))
    finally:
        app.dependency_overrides.pop(get_provider, None)
    assert r.status_code == 200
    gc.collect()
    assert len(refs) == 1 and refs[0]() is None


def test_only_a_count_and_an_estimate_are_stored(client, db, fake) -> None:
    assert post(client, png_with_text([SECRET_LINE, "עגבניות"])).status_code == 200
    rows = db.execute("SELECT month, provider, images, est_cost_usd FROM ocr_usage").fetchall()
    assert len(rows) == 1
    month, provider, images, usd = rows[0]
    assert (provider, images, float(usd)) == ("fake", 1, 0.0)
    assert month.day == 1
    dump = repr(db.execute("SELECT * FROM ocr_usage").fetchall())
    assert SECRET_LINE not in dump


def test_nothing_else_in_the_database_mentions_the_text(client, db, fake) -> None:
    assert post(client, png_with_text([SECRET_LINE]), "receipt").status_code == 200
    tables = [
        r[0]
        for r in db.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        ).fetchall()
    ]
    for table in tables:
        hit = db.execute(
            f'SELECT count(*) FROM "{table}" t WHERE t::text LIKE %s', (f"%{SECRET_LINE}%",)
        ).fetchone()[0]
        assert hit == 0, table
