"""Read a downloaded CSV or XLSX file into records, standard library only.

The CBS locality file (קובץ היישובים) is published as a spreadsheet; data.gov.il also offers CSV. No
openpyxl is needed: an XLSX is a zip of XML, and the few cell types a list like this uses (shared
strings, inline strings, numbers) are read here. Old binary XLS is not supported and says so.
The header row is the first of the first 30 rows that :func:`classify_fields` accepts, so a title
above the table does not matter.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from smartcart_ingest.geocode.localities import classify_fields

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_CELL_REF = re.compile(r"^([A-Z]+)")


class UnsupportedFile(ValueError):
    pass


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1255"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _column_index(ref: str) -> int:
    match = _CELL_REF.match(ref)
    n = 0
    for ch in match.group(1) if match else "A":
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_sheets(data: bytes) -> list[list[list[str]]]:
    """Every worksheet as a matrix of strings (empty cells are ``""``)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise UnsupportedFile("not a valid XLSX file") from exc
    names = set(zf.namelist())
    shared: list[str] = []
    if "xl/sharedStrings.xml" in names:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", _NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
    sheets = []
    for name in sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)):
        matrix: list[list[str]] = []
        root = ET.fromstring(zf.read(name))
        for row in root.iter(f"{{{_NS['m']}}}row"):
            cells: dict[int, str] = {}
            for c in row.findall("m:c", _NS):
                kind = c.get("t")
                if kind == "inlineStr":
                    text = "".join(t.text or "" for t in c.iter(f"{{{_NS['m']}}}t"))
                else:
                    v = c.find("m:v", _NS)
                    text = v.text or "" if v is not None else ""
                    if kind == "s" and text.isdigit() and int(text) < len(shared):
                        text = shared[int(text)]
                cells[_column_index(c.get("r", "A1"))] = text.strip()
            if cells:
                width = max(cells) + 1
                matrix.append([cells.get(i, "") for i in range(width)])
        sheets.append(matrix)
    return sheets


def csv_matrix(data: bytes) -> list[list[str]]:
    text = decode_text(data)
    head = text[:4096]
    if head.lstrip().startswith("<"):
        raise UnsupportedFile("the body is HTML, not a table (a block or error page)")
    delimiter = max(",;\t", key=lambda d: head.count(d))
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text), delimiter=delimiter)]


def matrix_to_records(matrix: list[list[str]]) -> list[dict[str, Any]]:
    """Records keyed by the header row (the first of the first 30 rows that looks like one)."""
    for i, row in enumerate(matrix[:30]):
        headers = [h for h in row if h]
        if len(headers) >= 2 and classify_fields(headers):
            keys = [h or f"_col{j}" for j, h in enumerate(row)]
            return [
                {k: (r[j] if j < len(r) else "") for j, k in enumerate(keys)}
                for r in matrix[i + 1 :]
                if any(r)
            ]
    return []


def read_records(data: bytes) -> list[dict[str, Any]]:
    """Records of the first table in ``data`` that has a locality header; ``[]`` when none."""
    if data[:2] == b"PK":
        for sheet in xlsx_sheets(data):
            records = matrix_to_records(sheet)
            if records:
                return records
        return []
    if data[:4] == b"\xd0\xcf\x11\xe0":
        raise UnsupportedFile("binary XLS (Excel 97-2003) is not supported; use the CSV or XLSX")
    return matrix_to_records(csv_matrix(data))
