"""Decoding helpers: every encoding and container the chains are known to use."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from smartcart_ingest import xmlutil

FIXTURES = Path(__file__).parent / "fixtures" / "xmlutil"
NAMES = ["חלב 3%", "לחם אחיד"]


def _names(xml: bytes) -> list[str]:
    return [xmlutil.scalar_children(row)["itemname"] for row in xmlutil.iter_rows(xml, {"Item"})]


@pytest.mark.parametrize(
    ("fixture", "encoding", "container"),
    [
        ("utf8.xml", "utf-8", "plain"),
        ("utf8_bom.xml", "utf-8-sig", "plain"),
        ("utf16le_bom.xml", "utf-16-le", "plain"),
        ("utf16be_bom.xml", "utf-16-be", "plain"),
        ("utf16le_nobom.xml", "utf-16-le", "plain"),
        ("cp1255.xml", "windows-1255", "plain"),
        ("cp1255_nodecl.xml", "windows-1255", "plain"),
        ("iso88598_decl_utf8.xml", "utf-8", "plain"),
        ("utf8.xml.gz", "utf-8", "gzip"),
        ("utf8.zip", "utf-8", "zip"),
        ("zip_named.gz", "utf-8", "zip"),
        ("nested_zip_in_gzip.gz", "utf-8", "gzip"),
    ],
)
def test_decode_every_encoding_and_container(fixture: str, encoding: str, container: str) -> None:
    decoded = xmlutil.decode((FIXTURES / fixture).read_bytes())
    assert decoded.encoding == encoding
    assert decoded.container == container
    assert decoded.data.startswith(b"<?xml") or decoded.data.startswith(b"<Root")
    assert _names(decoded.data) == NAMES


def test_plain_utf8_is_not_copied() -> None:
    data = (FIXTURES / "utf8.xml").read_bytes()
    assert xmlutil.to_utf8(data)[0] is data


def test_declaration_is_rewritten_to_utf8() -> None:
    out, enc = xmlutil.to_utf8((FIXTURES / "cp1255.xml").read_bytes())
    assert enc == "windows-1255"
    assert out.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')
    assert xmlutil.declared_encoding(out) == "utf-8"


def test_zip_prefers_xml_member_over_first_member() -> None:
    payload, container = xmlutil.unwrap((FIXTURES / "utf8.zip").read_bytes())
    assert container == "zip"
    assert payload.lstrip().startswith(b"<?xml")


@pytest.mark.parametrize(("fixture", "message"), [("truncated.gz", "gzip"), ("empty.gz", "empty")])
def test_broken_containers_raise(fixture: str, message: str) -> None:
    with pytest.raises(xmlutil.XmlDecodeError, match=message):
        xmlutil.decode((FIXTURES / fixture).read_bytes())


def test_empty_bytes_raise() -> None:
    with pytest.raises(xmlutil.XmlDecodeError, match="empty"):
        xmlutil.decode(b"")


def test_corrupt_zip_raises() -> None:
    with pytest.raises(xmlutil.XmlDecodeError, match="zip"):
        xmlutil.decode(b"PK\x03\x04garbage")


def test_malformed_xml_raises_on_rows() -> None:
    with pytest.raises(xmlutil.XmlDecodeError):
        list(xmlutil.iter_rows(b"<Root><Items><Item><ItemCode>1</Item></Items>", {"Item"}))


def test_read_header_stops_at_first_row() -> None:
    rows = b"".join(b"<Item><ItemCode>%d</ItemCode></Item>" % i for i in range(50_000))
    xml = (
        b"<Root><ChainId>7290027600007</ChainId><StoreId>001</StoreId><Items>"
        + rows
        + b"</Items></Root>"
    )
    root = xmlutil.read_header(xml, {"Item"})
    assert xmlutil.localname(root) == "Root"
    assert xmlutil.scalar_children(root)["chainid"] == "7290027600007"
    items = root.find("Items")
    # lxml feeds the parser in buffered chunks, so a few rows may be built, never the whole file.
    assert items is not None and 1 <= len(items) < 50_000


def test_read_header_ignores_root_with_row_name() -> None:
    root = xmlutil.read_header(
        b"<Store><Branches><Branch><StoreID>1</StoreID></Branch></Branches></Store>",
        {"Store", "Branch"},
    )
    assert xmlutil.localname(root) == "Store"


def test_iter_rows_never_yields_root_and_clears_rows() -> None:
    xml = b"<Item><Items><Item><A>1</A></Item><Item><A>2</A></Item></Items></Item>"
    seen = []
    parents = []
    for row in xmlutil.iter_rows(xml, {"Item"}):
        seen.append(xmlutil.scalar_children(row)["a"])
        parents.append(row.getprevious())
    assert seen == ["1", "2"]
    assert parents == [None, None]  # rows already consumed are freed before the next yield


def test_localname_strips_namespace() -> None:
    root = etree.fromstring(
        b'<asx:abap xmlns:asx="http://www.sap.com/abapxml"><asx:values/></asx:abap>'
    )
    assert xmlutil.localname(root) == "abap"
    assert xmlutil.localname(root[0]) == "values"


def test_scalar_children_lowercases_and_skips_nested() -> None:
    el = etree.fromstring(
        b"<Row><ChainID> 1 </ChainID><Clubs><ClubId>0</ClubId></Clubs><chainid>2</chainid></Row>"
    )
    assert xmlutil.scalar_children(el) == {"chainid": "1"}


def test_entities_are_not_resolved() -> None:
    xml = (
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/hostname">]>'
        b"<Root><Items><Item><ItemName>&x;</ItemName></Item></Items></Root>"
    )
    rows = [
        xmlutil.scalar_children(r).get("itemname", "") for r in xmlutil.iter_rows(xml, {"Item"})
    ]
    assert rows == [""]
