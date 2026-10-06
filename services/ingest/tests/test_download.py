"""Downloads by content hash, the raw store and the scraper wrapper (issue #37)."""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from smartcart_ingest import tracking
from smartcart_ingest.download import (
    PortalError,
    RemoteFile,
    ScraperFetcher,
    download,
    normalize_store_code,
    order_for_processing,
    parse_filename,
    sha256_hex,
)
from smartcart_ingest.rawstore import (
    LocalRawStore,
    RawStoreKeyError,
    S3RawStore,
    raw_key,
    rawstore_from_settings,
)
from smartcart_ingest.settings import Settings
from tests.fakes import ISRAEL, NOW, FakeAdapter, FakeFetcher, encode, item

# --- filenames ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "store", "published"),
    [
        ("PriceFull7290027600007-001-202610060600.gz", "001", datetime(2026, 10, 6, 6, 0)),
        ("Price7290058140886-012-202610061420.xml", "012", datetime(2026, 10, 6, 14, 20)),
        ("Promo7290700100008-000-207-20250224-103225.gz", "207", datetime(2025, 2, 24, 10, 32, 25)),
        ("Stores7290027600007-000-202610060201", "000", datetime(2026, 10, 6, 2, 1)),
    ],
)
def test_parse_filename(name, store, published) -> None:
    got_store, got_ts = parse_filename(name)
    assert got_store == store
    assert got_ts == published.replace(tzinfo=ISRAEL)


def test_parse_filename_tolerates_other_names() -> None:
    assert parse_filename("something.xml") == (None, None)


def test_normalize_store_code() -> None:
    assert normalize_store_code("001") == "1"
    assert normalize_store_code("000") == "0"
    assert normalize_store_code(" 12 ") == "12"
    assert normalize_store_code("") is None and normalize_store_code(None) is None


def test_order_puts_stores_then_fulls_then_deltas() -> None:
    names = [
        "Promofake-1-202610061100.gz",
        "Pricefake-1-202610060700.gz",
        "PriceFullfake-1-202610060600.gz",
        "Storesfake-000-202610060500.gz",
        "PromoFullfake-1-202610060600.gz",
        "Pricefake-1-202610060630.gz",
    ]
    ordered = order_for_processing([RemoteFile("fake", n) for n in names], FakeAdapter())
    assert [r.name for r in ordered] == [
        "Storesfake-000-202610060500.gz",
        "PriceFullfake-1-202610060600.gz",
        "PromoFullfake-1-202610060600.gz",
        "Pricefake-1-202610060630.gz",
        "Pricefake-1-202610060700.gz",
        "Promofake-1-202610061100.gz",
    ]


# --- raw store ---------------------------------------------------------------------------------


def test_raw_key_uses_the_israel_day() -> None:
    # 22:30 UTC on Oct 6 is 01:30 on Oct 7 in Israel.
    ts = datetime.fromisoformat("2026-10-06T22:30:00+00:00")
    assert (
        raw_key("7290027600007", ts, "PriceFull.gz") == "raw/7290027600007/2026/10/07/PriceFull.gz"
    )
    assert raw_key("c", ts, "../../etc/passwd") == "raw/c/2026/10/07/passwd"


def test_local_raw_store_roundtrip(tmp_path: Path) -> None:
    store = LocalRawStore(tmp_path)
    key = "raw/fake/2026/10/06/a.gz"
    assert not store.exists(key)
    store.put(key, b"abc")
    assert store.exists(key) and store.get(key) == b"abc"
    store.put(key, b"def")
    assert store.get(key) == b"def"
    assert not list(tmp_path.rglob(".tmp-*"))
    for bad in ("../x", "/abs", "a/../../b", ""):
        with pytest.raises(RawStoreKeyError):
            store.put(bad, b"x")


class _FakeClientError(Exception):
    def __init__(self, code: str) -> None:
        self.response = {"Error": {"Code": code}}


class _FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, Bucket, Key, Body):  # noqa: N803 - boto3 names
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):  # noqa: N803
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def head_object(self, Bucket, Key):  # noqa: N803
        if (Bucket, Key) not in self.objects:
            raise _FakeClientError("404")
        return {}


def test_s3_raw_store_is_a_thin_wrapper() -> None:
    client = _FakeS3()
    store = S3RawStore("bucket", client)
    assert not store.exists("raw/a")
    store.put("raw/a", b"x")
    assert store.exists("raw/a") and store.get("raw/a") == b"x"
    assert ("bucket", "raw/a") in client.objects

    class Denied(_FakeS3):
        def head_object(self, Bucket, Key):  # noqa: N803
            raise _FakeClientError("403")

    with pytest.raises(_FakeClientError):
        S3RawStore("bucket", Denied()).exists("raw/a")


def test_rawstore_from_settings(tmp_path: Path) -> None:
    assert isinstance(rawstore_from_settings(Settings(raw_store_path=tmp_path)), LocalRawStore)
    s3 = rawstore_from_settings(
        Settings(s3_bucket="b", s3_region="auto", s3_access_key_id="k", s3_secret_access_key="s",
                 s3_endpoint_url="https://example.invalid")
    )  # fmt: skip
    assert isinstance(s3, S3RawStore) and s3.bucket == "b"
    with pytest.raises(ValueError, match="RAW_STORE_PATH"):
        rawstore_from_settings(Settings(raw_store_path=None, s3_bucket=""))


# --- ScraperFetcher without the network --------------------------------------------------------


def test_scraper_fetcher_reads_and_removes_staged_files(tmp_path: Path) -> None:
    staged = tmp_path / "PriceFull7290027600007-001-202610060600.gz"
    staged.write_bytes(b"payload")
    fetcher = ScraperFetcher(staging_root=tmp_path)
    remote = RemoteFile("7290027600007", staged.name, local_path=str(staged))
    assert fetcher.fetch(remote) == b"payload"
    assert not staged.exists()
    with pytest.raises(PortalError):
        fetcher.fetch(remote)
    with pytest.raises(PortalError, match="not staged"):
        fetcher.fetch(RemoteFile("7290027600007", "x.gz"))


def test_scraper_fetcher_rejects_unmapped_chains() -> None:
    with pytest.raises(PortalError, match="no upstream scraper"):
        ScraperFetcher().list_files("fake")


def test_scraper_fetcher_maps_every_d13_chain_to_an_active_upstream_scraper() -> None:
    from smartcart_ingest.download import UPSTREAM_SCRAPERS, load_upstream

    ScraperFactory, _ = load_upstream()  # noqa: N806
    from smartcart_ingest.scheduler import D13_CHAINS

    assert set(UPSTREAM_SCRAPERS) == {c.chain_id for c in D13_CHAINS}
    for name in UPSTREAM_SCRAPERS.values():
        assert hasattr(ScraperFactory, name)
        assert not ScraperFactory.is_deprecated(name)


# --- download (database) -----------------------------------------------------------------------


def _setup(tmp_path: Path) -> tuple[FakeFetcher, LocalRawStore, FakeAdapter]:
    return FakeFetcher(), LocalRawStore(tmp_path), FakeAdapter()


@pytest.mark.db
def test_new_file_is_archived_and_tracked(db, tmp_path: Path) -> None:
    fetcher, store, adapter = _setup(tmp_path)
    data = encode(items=[item("A")])
    remote = fetcher.add("price_full", data, store_code="001", at=NOW - timedelta(hours=1))
    res = download(db, fetcher, store, remote, adapter, now=NOW)
    assert res.outcome == "new"
    f = res.file
    assert f.status == "downloaded" and f.sha256 == sha256_hex(data)
    assert (f.kind, f.store_code, f.chain_id) == ("price_full", "1", "fake")
    assert f.published_at == NOW - timedelta(hours=1)
    assert f.path == f"raw/fake/2026/10/06/{remote.name}"
    assert store.get(f.path) == data


@pytest.mark.db
def test_hash_already_loaded_is_skipped_and_logged(db, tmp_path: Path) -> None:
    fetcher, store, adapter = _setup(tmp_path)
    remote = fetcher.add("price_full", encode(items=[item("A")]))
    first = download(db, fetcher, store, remote, adapter, now=NOW)
    tracking.mark_loading(db, first.file.id)
    tracking.mark_loaded(db, first.file.id, 1)
    # Same bytes again (a re-run, or the 08:30 pass), even under another name.
    again = fetcher.add("price_full", encode(items=[item("A")]), name="PriceFullfake-1-copy.gz")
    with capture_logs() as logs:
        res = download(db, fetcher, store, again, adapter, now=NOW)
    assert res.outcome == "skipped" and res.file.id == first.file.id
    assert tracking.get(db, first.file.id).status == "loaded"
    assert any(e["event"].startswith("skipped") and e["status"] == "loaded" for e in logs)
    assert (
        db.execute(
            "SELECT count(*) FROM file_tracking WHERE sha256 = %s", (first.file.sha256,)
        ).fetchone()[0]
        == 1
    )


@pytest.mark.db
def test_quarantined_hash_is_skipped(db, tmp_path: Path) -> None:
    fetcher, store, adapter = _setup(tmp_path)
    remote = fetcher.add("price_full", encode(items=[item("Q")]))
    res = download(db, fetcher, store, remote, adapter, now=NOW)
    tracking.mark_loading(db, res.file.id)
    tracking.record_quarantine(db, res.file.id, [("zero_price", "x")])
    assert download(db, fetcher, store, remote, adapter, now=NOW).outcome == "skipped"


@pytest.mark.db
def test_failed_file_is_resumed_and_keeps_its_failure(db, tmp_path: Path) -> None:
    fetcher, store, adapter = _setup(tmp_path)
    remote = fetcher.add("price_full", encode(items=[item("F")]))
    res = download(db, fetcher, store, remote, adapter, now=NOW)
    tracking.mark_failed(db, res.file.id, "parse failed: boom")
    again = download(db, fetcher, store, remote, adapter, now=NOW)
    assert again.outcome == "resumed" and again.file.status == "downloaded"
    assert again.file.reason == "retry after: parse failed: boom"


@pytest.mark.db
def test_same_filename_with_new_content_does_not_overwrite_the_archive(db, tmp_path) -> None:
    fetcher, store, adapter = _setup(tmp_path)
    name = "PriceFullfake-1-202610060600.gz"
    first = download(
        db, fetcher, store, fetcher.add("price_full", encode(salt="1"), name=name), adapter, now=NOW
    )
    fetcher.clear()
    second = download(
        db, fetcher, store, fetcher.add("price_full", encode(salt="2"), name=name), adapter, now=NOW
    )
    assert first.file.id != second.file.id
    assert first.file.path != second.file.path and "dup-" in second.file.path
    assert store.get(first.file.path) == encode(salt="1")
    assert store.get(second.file.path) == encode(salt="2")


@pytest.mark.db
def test_stores_file_has_no_store_code(db, tmp_path: Path) -> None:
    fetcher, store, adapter = _setup(tmp_path)
    res = download(db, fetcher, store, fetcher.add("stores", encode()), adapter, now=NOW)
    assert res.file.kind == "stores" and res.file.store_code is None


def _fake_upstream(monkeypatch, outcomes):
    """Replace the upstream scraper with one that 'downloads' ``outcomes`` (name, bytes|error)."""
    from smartcart_ingest.download import load_upstream

    load_upstream()
    import il_supermarket_scarper
    from il_supermarket_scarper.utils.files.file_entry import FileEntry
    from il_supermarket_scarper.utils.scraping.scraping_result import ScrapingResult

    seen: dict = {}

    class FakeScraper:
        def __init__(self, file_output=None, status_database=None):
            self.out = file_output

        async def scrape(self, files_types=None, when_date=None, **kw):
            seen.update(files_types=files_types, when_date=when_date)
            for name, payload in outcomes:
                entry = FileEntry(name=name, url=f"https://portal.invalid/{name}", size=None,
                                  published_at="2026-10-06T06:00:00")  # fmt: skip
                if isinstance(payload, bytes):
                    Path(self.out.storage_path, name).write_bytes(payload)
                    yield ScrapingResult(entry, True, None, True, saved_file_name=name)
                else:
                    yield ScrapingResult(entry, False, None, False, error=payload)

    monkeypatch.setattr(
        il_supermarket_scarper.ScraperFactory,
        "get",
        classmethod(lambda cls, name, **kw: FakeScraper),
    )
    return seen


def test_scraper_fetcher_wraps_upstream_listing(monkeypatch, tmp_path: Path) -> None:
    seen = _fake_upstream(monkeypatch, [("PriceFull7290027600007-001-202610060600.gz", b"gz")])
    fetcher = ScraperFetcher(staging_root=tmp_path)
    since = datetime(2026, 10, 6, tzinfo=ISRAEL)
    files = fetcher.list_files("7290027600007", ["price_full", "promo_full"], since)
    assert seen["files_types"] == ["PRICE_FULL_FILE", "PROMO_FULL_FILE"]
    assert seen["when_date"] == datetime(2026, 10, 6)
    (remote,) = files
    assert remote.name == "PriceFull7290027600007-001-202610060600.gz"
    assert remote.published_at == datetime(2026, 10, 6, 6, tzinfo=ISRAEL)
    assert fetcher.fetch(remote) == b"gz"
    fetcher.close()
    assert not list(tmp_path.iterdir())


def test_scraper_fetcher_raises_portal_error_when_nothing_downloaded(monkeypatch, tmp_path) -> None:
    _fake_upstream(monkeypatch, [("PriceFull7290027600007-001-202610060600.gz", "HTTP 503")])
    with pytest.raises(PortalError, match="HTTP 503"):
        ScraperFetcher(staging_root=tmp_path).list_files("7290027600007", ["price_full"])


def test_upstream_import_does_not_write_logging_log(tmp_path) -> None:
    """On the VPS the working directory is read-only; upstream must not open logging.log there.
    A fresh interpreter, so no earlier import in this session hides the problem."""
    import subprocess
    import sys

    code = (
        "import logging\n"
        "from smartcart_ingest.download import load_upstream, UPSTREAM_LOGGERS\n"
        "load_upstream()\n"
        "for n in UPSTREAM_LOGGERS:\n"
        "    assert not any(isinstance(h, logging.FileHandler) for h in logging.getLogger(n).handlers)\n"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True, timeout=120)
    assert not (tmp_path / "logging.log").exists()
