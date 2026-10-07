"""Shared decoding helpers for transparency files.

Chains publish the same regulated XML in different containers and encodings:

* containers: gzip (most portals), zip (some Cerberus files keep a ``.gz`` name but are zip),
  or plain XML (Cerberus Stores files);
* encodings: UTF-8 with or without a BOM, UTF-16 (LE/BE, with or without a BOM) and
  windows-1255, sometimes with an XML declaration that names a different encoding than the
  bytes actually use (``ISO-8859-8`` declared over UTF-8 content is common).

Everything here works on bytes and returns UTF-8 XML bytes or lxml elements. Nothing in this
module knows about chains; adapters wrap :class:`XmlDecodeError` into ``AdapterError`` so the
alert names the chain.
"""

from __future__ import annotations

import gzip
import io
import re
import zipfile
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from lxml import etree

GZIP_MAGIC = b"\x1f\x8b"
ZIP_MAGIC = b"PK\x03\x04"
MAX_NESTING = 3
"""A gzip that contains a zip (or the reverse) is unwrapped up to this depth."""

_XML_DECL = re.compile(rb"^\s*<\?xml[^>]*\?>", re.IGNORECASE)
_DECL_ENCODING = re.compile(rb"""encoding\s*=\s*["']([A-Za-z0-9._:-]+)["']""", re.IGNORECASE)

_HEBREW_SINGLE_BYTE = {"windows-1255", "cp1255", "iso-8859-8", "iso-8859-8-i", "iso8859-8"}


class XmlDecodeError(ValueError):
    """The bytes could not be unwrapped, decoded or parsed as XML."""


@dataclass(frozen=True)
class DecodedXml:
    """UTF-8 XML bytes ready for lxml, plus what was detected on the way."""

    data: bytes
    encoding: str
    """Detected source encoding: utf-8, utf-8-sig, utf-16-le, utf-16-be or windows-1255."""
    container: str
    """Outermost container: gzip, zip or plain."""


# --------------------------------------------------------------------------- containers


def unwrap(data: bytes) -> tuple[bytes, str]:
    """Strip gzip/zip containers by magic bytes (never by filename).

    Returns the payload and the outermost container name. A zip yields its first ``.xml``
    member, or its first member when none ends in ``.xml``.
    """
    outer = "plain"
    for depth in range(MAX_NESTING):
        if data[:2] == GZIP_MAGIC:
            kind = "gzip"
            try:
                data = gzip.decompress(data)
            except (OSError, EOFError, zlib.error) as exc:
                raise XmlDecodeError(f"corrupt gzip container: {exc}") from exc
        elif data[:4] == ZIP_MAGIC:
            kind = "zip"
            data = _first_zip_member(data)
        else:
            break
        if depth == 0:
            outer = kind
    return data, outer


def _first_zip_member(data: bytes) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            members = [m for m in zf.infolist() if not m.is_dir()]
            if not members:
                raise XmlDecodeError("zip container has no members")
            xml_members = [m for m in members if m.filename.lower().endswith(".xml")]
            return zf.read((xml_members or members)[0])
    except (zipfile.BadZipFile, zlib.error, EOFError) as exc:
        raise XmlDecodeError(f"corrupt zip container: {exc}") from exc


# --------------------------------------------------------------------------- encodings


def detect_encoding(data: bytes) -> str:
    """Detect the real encoding of XML bytes.

    Order: BOM, UTF-16 without BOM (NUL byte pattern around ``<``), strict UTF-8, then the
    declared single-byte Hebrew encoding, then windows-1255 as the last resort. The declaration
    is trusted only when the bytes are not valid UTF-8, because ISO-8859-8 is often declared
    over UTF-8 content.
    """
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if data.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if data.startswith(b"\xfe\xff"):
        return "utf-16-be"
    head = data[:4]
    if head[:2] == b"<\x00":
        return "utf-16-le"
    if head[:2] == b"\x00<":
        return "utf-16-be"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    declared = declared_encoding(data)
    if declared in _HEBREW_SINGLE_BYTE or declared is None:
        return "windows-1255"
    try:
        data.decode(declared)
        return declared
    except (LookupError, UnicodeDecodeError):
        return "windows-1255"


def declared_encoding(data: bytes) -> str | None:
    """The encoding named in an ASCII-compatible XML declaration, lowercased, or None."""
    match = _XML_DECL.match(data[:200])
    if not match:
        return None
    enc = _DECL_ENCODING.search(match.group(0))
    return enc.group(1).decode("ascii").lower() if enc else None


def to_utf8(data: bytes) -> tuple[bytes, str]:
    """Return ``(utf8_bytes, detected_encoding)`` with the XML declaration rewritten to UTF-8.

    Plain UTF-8 input with a UTF-8 (or no) declaration is returned unchanged, so the common
    case costs no copy.
    """
    encoding = detect_encoding(data)
    if encoding == "utf-8" and declared_encoding(data) in (None, "utf-8", "utf8"):
        return data, encoding
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError as exc:
        raise XmlDecodeError(f"cannot decode as {encoding}: {exc}") from exc
    text = text.lstrip("﻿")
    out = text.encode("utf-8")
    out = _XML_DECL.sub(b'<?xml version="1.0" encoding="UTF-8"?>', out, count=1)
    return out, encoding


def decode(data: bytes) -> DecodedXml:
    """Unwrap containers and normalise the encoding. Raises XmlDecodeError on failure."""
    if not data:
        raise XmlDecodeError("file is empty (0 bytes)")
    payload, container = unwrap(data)
    if not payload.strip():
        raise XmlDecodeError(f"{container} container holds an empty payload")
    utf8, encoding = to_utf8(payload)
    return DecodedXml(data=utf8, encoding=encoding, container=container)


# --------------------------------------------------------------------------- parsing


def localname(element: etree._Element) -> str:
    """Tag without namespace (Shufersal Stores use the SAP ``asx:`` namespace)."""
    tag = element.tag
    if not isinstance(tag, str):  # comments, processing instructions
        return ""
    return tag.rsplit("}", 1)[-1]


def _iterparse(xml: bytes, events: tuple[str, ...]) -> Iterator[tuple[str, etree._Element]]:
    return etree.iterparse(
        io.BytesIO(xml),
        events=events,
        huge_tree=True,
        resolve_entities=False,
        no_network=True,
        remove_comments=True,
    )


def read_header(xml: bytes, row_tags: Iterable[str]) -> etree._Element:
    """Parse until the first row element starts and return the (partial) root.

    The returned root holds every header field that precedes the rows (ChainId, StoreId,
    SubChainName, a schema marker...) and the open container chain down to the first row,
    which is what schema and kind detection need. Files with no rows are parsed fully.
    """
    rows = set(row_tags)
    root: etree._Element | None = None
    depth = 0
    try:
        for event, elem in _iterparse(xml, ("start", "end")):
            if event == "start":
                depth += 1
                if root is None:
                    root = elem
                elif depth >= 2 and localname(elem) in rows:
                    break
            else:
                depth -= 1
    except etree.XMLSyntaxError as exc:
        if root is None:
            raise XmlDecodeError(f"not well-formed XML: {exc}") from exc
        raise XmlDecodeError(f"XML breaks inside the header: {exc}") from exc
    if root is None:
        raise XmlDecodeError("no XML root element")
    return root


def iter_rows(xml: bytes, row_tags: Iterable[str]) -> Iterator[etree._Element]:
    """Stream row elements (never the root) whose local name is in ``row_tags``.

    Each element is complete when yielded (children included) and is cleared as soon as the
    caller asks for the next one, so memory stays flat on 100 MB PriceFull files. Copy what
    you need before advancing.
    """
    rows = set(row_tags)
    try:
        for _event, elem in _iterparse(xml, ("end",)):
            parent = elem.getparent()
            if parent is None or localname(elem) not in rows:
                continue
            while elem.getprevious() is not None:  # rows already consumed
                del parent[0]
            yield elem
            elem.clear(keep_tail=False)
    except etree.XMLSyntaxError as exc:
        raise XmlDecodeError(f"not well-formed XML: {exc}") from exc


def scalar_children(element: etree._Element) -> dict[str, str]:
    """Direct leaf children as ``{lowercased localname: stripped text}``.

    Lowercasing makes ChainId / ChainID / CHAINID one key. The first occurrence wins.
    """
    out: dict[str, str] = {}
    for child in element:
        if len(child):
            continue
        name = localname(child).lower()
        if name and name not in out:
            out[name] = (child.text or "").strip()
    return out
