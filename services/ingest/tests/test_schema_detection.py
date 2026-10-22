"""Schema detection is strict: a file in a model this code does not know is never parsed as v1
(issue #57, phase 3 "adaptation to the authority's new reporting schema").

No official specification and no real new-model file was reachable on 2026-10-22 (docs/adapters.md,
"Schema versions"), so there is **no v2 field mapping to test**. What is tested here is the
safety net around the placeholder: every signal of a different model ends in ``unknown`` (the
file is quarantined with a reason and an alert), and the 21 real files of 2026-10-21 stay ``v1``.
All inline documents are synthetic.
"""

from __future__ import annotations

import gzip
import json
from datetime import timedelta
from pathlib import Path

import pytest

from smartcart_ingest.adapters import get_adapter
from smartcart_ingest.adapters._common import (
    CONTAINERS,
    INFORMATIONAL_VERSION_FIELDS,
    PROVISIONAL_V2_MARKER,
    UNSUPPORTED_VERSION_FIELDS,
    RegulationAdapter,
)
from smartcart_ingest.adapters.base import AdapterError, UnknownSchemaError
from smartcart_ingest.alerts import Alerter
from smartcart_ingest.rawstore import LocalRawStore
from smartcart_ingest.scheduler import Scheduler
from smartcart_ingest.settings import Settings
from tests.fakes import FakeFetcher, RecordingSink
from tests.test_adapters import FIXTURES, chain_adapters

ADAPTERS = sorted(chain_adapters().values(), key=lambda c: c.slug)


def price_doc(cls: type[RegulationAdapter], *, root_attrs: str = "", header: str = "") -> bytes:
    """A minimal PriceFull in the chain's own price container."""
    container = next(c for c in sorted(cls.containers) if CONTAINERS[c][0] == "price")
    row = CONTAINERS[container][1]
    return (
        f"<Root{root_attrs}><ChainId>{cls.chain_id}</ChainId><StoreId>1</StoreId>{header}"
        f"<{container}><{row}><ItemCode>7290004131074</ItemCode><ItemName>חלב 3%</ItemName>"
        f"<ItemPrice>7.12</ItemPrice></{row}></{container}></Root>"
    ).encode()


def inspect(cls: type[RegulationAdapter], doc: bytes) -> dict:
    return cls().inspect_schema(doc)


def parse(cls: type[RegulationAdapter], doc: bytes):
    adapter = cls()
    raw = adapter.raw_file_for(f"PriceFull{cls.chain_id}-001-202610060300.gz", doc)
    return adapter.parse(raw, doc)


# ---------------------------------------------------------------------------- the marker


@pytest.mark.parametrize("cls", ADAPTERS, ids=lambda c: c.slug)
def test_plain_file_is_v1_for_every_chain(cls) -> None:
    got = inspect(cls, price_doc(cls))
    assert got["schema"] == "v1"
    assert parse(cls, price_doc(cls)).raw.schema_version == "v1"


@pytest.mark.parametrize("cls", ADAPTERS, ids=lambda c: c.slug)
@pytest.mark.parametrize("value", ["2", "2.0", " 2.1.3 "])
def test_marker_major_2_is_v2_in_header_or_root_attribute(cls, value) -> None:
    name = PROVISIONAL_V2_MARKER.name
    in_header = price_doc(cls, header=f"<{name}>{value}</{name}>")
    in_root = price_doc(cls, root_attrs=f' {name.lower()}="{value}"')
    for doc in (in_header, in_root):
        assert inspect(cls, doc)["schema"] == "v2"
        assert parse(cls, doc).raw.schema_version == "v2"


@pytest.mark.parametrize("cls", ADAPTERS, ids=lambda c: c.slug)
@pytest.mark.parametrize("value", ["3.1", "1.0", "", "abc", "2x", "-2"])
def test_marker_with_any_other_major_is_unknown_never_v1(cls, value) -> None:
    name = PROVISIONAL_V2_MARKER.name
    doc = price_doc(cls, header=f"<{name}>{value}</{name}>")
    got = inspect(cls, doc)
    assert got["schema"] == "unknown"
    assert name in got["reason"] and repr(value.strip()) in got["reason"]
    with pytest.raises(UnknownSchemaError, match=name):
        parse(cls, doc)


# ---------------------------------------------------------------------------- other signals


@pytest.mark.parametrize("cls", ADAPTERS, ids=lambda c: c.slug)
@pytest.mark.parametrize("field", sorted(UNSUPPORTED_VERSION_FIELDS))
def test_other_declared_model_version_is_unknown(cls, field) -> None:
    for doc in (
        price_doc(cls, header=f"<{field}>4.0</{field}>"),
        price_doc(cls, root_attrs=f' {field}="4.0"'),
    ):
        assert inspect(cls, doc)["schema"] == "unknown"
        with pytest.raises(UnknownSchemaError, match="reporting-model version"):
            parse(cls, doc)


def test_version_field_names_are_matched_case_insensitively() -> None:
    cls = chain_adapters()["shufersal"]
    assert inspect(cls, price_doc(cls, header="<MODELVERSION>1</MODELVERSION>"))["schema"] == (
        "unknown"
    )


@pytest.mark.parametrize("attr", ["xsi:schemaLocation", "xsi:noNamespaceSchemaLocation"])
def test_root_pointing_at_an_xsd_is_unknown(attr) -> None:
    cls = chain_adapters()["ramilevy"]
    doc = price_doc(
        cls, root_attrs=f' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" {attr}="p.xsd"'
    )
    assert inspect(cls, doc)["schema"] == "unknown"
    with pytest.raises(UnknownSchemaError, match="XSD"):
        parse(cls, doc)


def test_default_namespace_on_the_root_is_unknown() -> None:
    cls = chain_adapters()["osherad"]
    doc = price_doc(cls, root_attrs=' xmlns="urn:example:price-reporting:2"')
    got = inspect(cls, doc)
    assert got["schema"] == "unknown" and "namespace" in got["reason"]
    assert got["signature"]["namespaces"] == ["urn:example:price-reporting:2"]
    with pytest.raises(UnknownSchemaError, match="namespace"):
        parse(cls, doc)


def test_a_namespace_prefix_declaration_alone_is_still_v1() -> None:
    """The real Cerberus-style files declare ``xmlns:xsi`` on the root; that is not a model."""
    cls = chain_adapters()["osherad"]
    doc = price_doc(cls, root_attrs=' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
    assert inspect(cls, doc)["schema"] == "v1"
    assert parse(cls, doc).raw.schema_version == "v1"


def test_issuing_software_stamps_do_not_change_the_schema_but_are_reported() -> None:
    cls = chain_adapters()["tivtaam"]
    doc = price_doc(cls, header="<XmlDocVersion>5.0</XmlDocVersion><DllVerNo>8.0.1.3</DllVerNo>")
    got = inspect(cls, doc)
    assert got["schema"] == "v1"
    assert got["signature"]["declared_versions"] == {"xmldocversion": "5.0", "dllverno": "8.0.1.3"}
    assert set(got["signature"]["declared_versions"]) == set(INFORMATIONAL_VERSION_FIELDS)
    assert parse(cls, doc).raw.schema_version == "v1"


def test_marker_wins_over_the_other_signals() -> None:
    cls = chain_adapters()["shufersal"]
    doc = price_doc(cls, header="<SchemaVersion>2.0</SchemaVersion><ModelVersion>9</ModelVersion>")
    assert inspect(cls, doc)["schema"] == "v2"


@pytest.mark.parametrize("cls", ADAPTERS, ids=lambda c: c.slug)
def test_unrecognised_container_is_unknown_with_the_expected_ones_named(cls) -> None:
    doc = f"<Root><ChainId>{cls.chain_id}</ChainId><Catalogue><Entry/></Catalogue></Root>".encode()
    got = inspect(cls, doc)
    assert got["schema"] == "unknown" and "no container this chain uses" in got["reason"]
    with pytest.raises(UnknownSchemaError) as info:
        parse(cls, doc)
    assert cls.chain_id in str(info.value) and "expected one of" in str(info.value)


def test_a_new_model_that_renames_the_rows_fails_loudly_not_silently() -> None:
    """No marker, the old container, a renamed item field: not parsed as v1 with empty prices."""
    cls = chain_adapters()["shufersal"]
    doc = (
        f"<Root><ChainId>{cls.chain_id}</ChainId><StoreId>1</StoreId><Items><Item>"
        "<Barcode>7290004131074</Barcode><Name>חלב</Name><Price>7.12</Price></Item></Items></Root>"
    ).encode()
    with pytest.raises(AdapterError, match="missing ItemCode"):
        parse(cls, doc)


# ---------------------------------------------------------------------------- inspect_schema


def test_inspect_schema_never_raises_on_bad_bytes() -> None:
    cls = chain_adapters()["shufersal"]
    for data in (b"", b"not xml at all", gzip.compress(b"<html>expired")[:12], b"<a><b></a>"):
        got = inspect(cls, data)
        assert got["schema"] == "unreadable" and got["error"]


def test_inspect_schema_signature_lists_the_header_for_the_probe() -> None:
    cls = chain_adapters()["yohananof"]
    got = inspect(cls, price_doc(cls, header="<BikoretNo>0</BikoretNo>"))
    sig = got["signature"]
    assert sig["root"] == "Root" and sig["containers"] == ["Items"]
    assert {"chainid", "storeid", "bikoretno"} <= set(sig["header_fields"])
    assert sig["declared_versions"] == {} and sig["namespaces"] == []


# ---------------------------------------------------------------------------- real files


def real_files() -> list[tuple[str, Path]]:
    return [
        (p.parent.parent.name, p)
        for p in sorted(FIXTURES.glob("*/real/*"))
        if p.suffix != ".json" and p.is_file()
    ]


def test_there_are_real_files_to_check() -> None:
    assert len(real_files()) >= 21


@pytest.mark.parametrize(("slug", "path"), real_files(), ids=lambda v: getattr(v, "name", v))
def test_every_real_file_is_v1_and_declares_no_version(slug, path) -> None:
    """Verified on the files of 2026-10-21 (7 chains): none carries any version marker, so all
    are v1 by the container rule. The day one does, this test names the file."""
    got = chain_adapters()[slug]().inspect_schema(path.read_bytes())
    assert got["schema"] == "v1", (path.name, got.get("reason"))
    assert got["signature"]["declared_versions"] == {}, path.name
    assert got["signature"]["namespaces"] == [], path.name
    manifest = json.loads((path.parent / "MANIFEST.json").read_text(encoding="utf-8"))
    recorded = {f["file"]: f["schema"] for f in manifest["files"]}
    assert recorded.get(path.name, "v1") == "v1"


# ---------------------------------------------------------------------------- the pipeline


@pytest.mark.db
@pytest.mark.parametrize(
    ("header", "reason_part"),
    [
        ("<SchemaVersion>3.1</SchemaVersion>", "SchemaVersion='3.1'"),
        ("<ModelVersion>4.0</ModelVersion>", "reporting-model version"),
    ],
)
def test_unknown_schema_file_is_quarantined_with_the_reason_and_never_loaded(
    db, tmp_path, header, reason_part
) -> None:
    cls = chain_adapters()["shufersal"]
    adapter = get_adapter(cls.chain_id)
    doc = price_doc(cls, header=header)
    name = f"PriceFull{cls.chain_id}-001-202610060300.gz"
    fetcher = FakeFetcher()
    fetcher.add("price_full", gzip.compress(doc, mtime=0), chain_id=cls.chain_id, name=name)
    now = adapter.parse_filename(name).published_at + timedelta(hours=1)
    sink = RecordingSink()
    sched = Scheduler(
        db,
        fetcher,
        LocalRawStore(tmp_path),
        Alerter([sink]),
        Settings(),
        adapter_for=get_adapter,
        now=lambda: now,
        sleep=lambda s: None,
    )
    report = sched.run_full([cls.chain_id]).chains[0]
    assert (report.loaded, report.failed) == (0, 1)
    (alert,) = sink.alerts
    assert alert.kind == "unknown_schema" and cls.chain_id in alert.message
    assert reason_part in alert.message
    row = db.execute(
        "SELECT status, reason FROM file_tracking WHERE chain_id = %s", (cls.chain_id,)
    ).fetchone()
    assert row[0] == "failed" and row[1].startswith("unknown schema:") and reason_part in row[1]
    assert db.execute("SELECT count(*) FROM prices").fetchone()[0] == 0
