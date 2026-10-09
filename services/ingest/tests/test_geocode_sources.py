"""The locality sources: the HTTP helper's User-Agent, the Wikidata parser and the fetch script's
per-source report, preference order and failure exit code. No network."""

from __future__ import annotations

import importlib.util
import json
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from smartcart_ingest.geocode import ckan, http, tables, wikidata
from smartcart_ingest.geocode.http import HttpFailure, StatusLog, get_json
from smartcart_ingest.geocode.localities import load_localities, localities_from_records

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "data" / "geo" / "fixtures"
LOCALITIES = json.loads((FIXTURES / "wikidata_localities.json").read_text(encoding="utf-8"))
PROPERTY = json.loads((FIXTURES / "wikidata_property.json").read_text(encoding="utf-8"))


# --- HTTP helper ---------------------------------------------------------------------------------


class _Resp:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body, self.status = body, status

    def read(self, *_a) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_a) -> None:
        return None


def test_every_request_has_a_descriptive_user_agent_and_accept(monkeypatch) -> None:
    seen = []

    def fake_urlopen(req, timeout):
        seen.append(req)
        return _Resp(b'{"ok": true}')

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.delenv("GEO_CONTACT", raising=False)
    monkeypatch.delenv("NOMINATIM_CONTACT", raising=False)
    log = StatusLog()
    assert get_json("https://data.gov.il/api/3/action/x?q=1", log=log) == {"ok": True}
    get_json("https://query.wikidata.org/sparql?query=x", accept=wikidata.ACCEPT, log=log)
    ua = seen[0].get_header("User-agent")
    assert ua.startswith("SmartCart-geo/") and "github.com/NoaMcDa/SmartCart" in ua and "contact:" in ua
    assert "Python-urllib" not in ua and "Mozilla" not in ua  # honest, no browser impersonation
    assert seen[0].get_header("Accept") == "application/json"
    assert seen[1].get_header("Accept") == wikidata.ACCEPT
    assert log.summary() == "HTTP 200 x2"
    monkeypatch.setenv("NOMINATIM_CONTACT", "ops@example.org")
    assert "ops@example.org" in http.user_agent()


def test_http_failure_carries_the_status(monkeypatch) -> None:
    def forbidden(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(http.urllib.request, "urlopen", forbidden)
    log = StatusLog()
    with pytest.raises(HttpFailure) as err:
        get_json("https://data.gov.il/api/3/action/x", log=log)
    assert err.value.status == 403 and "403" in str(err.value)
    assert log.summary() == "HTTP 403 x1" and log.last_failure() == 403


# --- Wikidata parsing ----------------------------------------------------------------------------


def test_property_discovery_picks_the_locality_code_not_other_cbs_ids() -> None:
    prop, candidates = wikidata.pick_property(PROPERTY)
    assert prop == "P99999" and len(candidates) == 2
    assert wikidata.pick_property({"results": {"bindings": []}}) == (None, [])
    only_other = {"results": {"bindings": [PROPERTY["results"]["bindings"][0]]}}
    assert wikidata.pick_property(only_other)[0] is None  # nothing about localities: no guess


def test_locality_query_is_one_select_on_the_property_and_p625() -> None:
    query = wikidata.locality_query("P99999")
    assert "wdt:P99999" in query and "wdt:P625" in query
    url = wikidata.sparql_url(query)
    assert url.startswith("https://query.wikidata.org/sparql?")
    assert urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["query"][0] == query
    with pytest.raises(ValueError):
        wikidata.locality_query("P1; DROP")


def test_parse_localities_from_a_recorded_shape_response() -> None:
    rows, skipped = wikidata.parse_localities(LOCALITIES, retrieved_at="2026-10-09")
    by_code = {r.code: r for r in rows}
    assert sorted(by_code) == ["3000", "4000", "5000", "874"]  # zero-padded 0874 normalized
    tel_aviv = by_code["5000"]
    assert (tel_aviv.name_he, tel_aviv.name_en) == ("תל אביב-יפו", "Tel Aviv-Yafo")
    assert (tel_aviv.lat, tel_aviv.lon) == (32.08, 34.78)  # Point(lon lat): the order is swapped
    assert tel_aviv.source == "wikidata" and tel_aviv.retrieved_at == "2026-10-09"
    assert by_code["4000"].name_he == "חיפה (פריט כפול)"  # the lowest Q-id wins a duplicate code
    assert skipped == {
        "no_code": 1,
        "bad_point": 1,
        "outside_israel": 1,
        "no_name": 1,
        "duplicate_codes": 1,
    }


SEARCH = json.loads((FIXTURES / "wikidata_search.json").read_text(encoding="utf-8"))
SIGNATURE = json.loads((FIXTURES / "wikidata_signature.json").read_text(encoding="utf-8"))


def wikidata_router(*, search=SEARCH, signature=SIGNATURE, urls: list[str] | None = None):
    """A fake for every Wikidata request: the search API, the three SPARQL queries."""

    def fetch(url: str):
        if urls is not None:
            urls.append(url)
        if url.startswith(wikidata.API):
            return search
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["query"][0]
        if "VALUES" in query:
            return signature
        if "central bureau of statistics" in query:
            return PROPERTY
        return LOCALITIES

    return fetch


def test_search_hits_are_parsed_and_scored() -> None:
    hits = wikidata.parse_search(SEARCH)
    assert [h[0] for h in hits] == ["P99999", "P88888", "P77777"]  # Q5 is not a property
    scores = {pid: wikidata.score_search_hit(label, desc) for pid, label, desc in hits}
    assert scores["P99999"] > 0 and scores["P88888"] == 0 and scores["P77777"] == 0


def test_discovery_prefers_the_property_that_holds_the_known_codes() -> None:
    lines: list[str] = []
    prop, how = wikidata.discover_property(wikidata_router(), lines.append)
    assert prop == "P99999" and "signature" in how
    text = "\n".join(lines)
    assert "P99999 | Israel Central Bureau of Statistics locality code | identifier of an Israeli" in text
    assert "P88888" in text and "matches 2 of 3" in text  # every candidate is logged


def test_discovery_falls_back_to_the_search_description_then_the_label_query() -> None:
    no_signature = {"results": {"bindings": []}}
    prop, how = wikidata.discover_property(wikidata_router(signature=no_signature))
    assert prop == "P99999" and how.startswith("search")
    nothing = {"search": []}
    prop, how = wikidata.discover_property(wikidata_router(search=nothing, signature=no_signature))
    assert prop == "P99999" and how == "label query"
    # one hit on the signature is not enough to be believed
    one = {"results": {"bindings": SIGNATURE["results"]["bindings"][2:]}}
    prop, _ = wikidata.discover_property(wikidata_router(search=nothing, signature=one))
    assert prop == "P99999"  # via the label query, not via the single signature hit P66666


def test_discovery_survives_failing_searches() -> None:
    def broken(url: str):
        if url.startswith(wikidata.API):
            raise HttpFailure(500, "HTTP 500")
        return wikidata_router()(url)

    lines: list[str] = []
    prop, how = wikidata.discover_property(broken, lines.append)
    assert prop == "P99999" and "signature" in how
    assert sum("error HttpFailure" in line for line in lines) == len(wikidata.SEARCH_TERMS)


def test_searches_cover_the_requested_terms() -> None:
    urls: list[str] = []
    wikidata.discover_property(wikidata_router(urls=urls))
    queries = [urllib.parse.parse_qs(urllib.parse.urlparse(u).query) for u in urls if u.startswith(wikidata.API)]
    assert {(q["language"][0], q["search"][0]) for q in queries} >= {
        ("en", "Central Bureau of Statistics"),
        ("en", "Israeli settlement"),
        ("he", "הלשכה המרכזית לסטטיסטיקה"),
        ("he", "סמל יישוב"),
    }
    assert all(q["action"] == ["wbsearchentities"] and q["type"] == ["property"] for q in queries)


def test_fetch_localities_discovers_then_runs_one_data_query() -> None:
    urls: list[str] = []
    rows, _skipped, prop = wikidata.fetch_localities(wikidata_router(urls=urls), retrieved_at="d")
    assert prop == "P99999" and len(rows) == 4
    sparql = [u for u in urls if u.startswith(wikidata.ENDPOINT)]
    data_queries = [u for u in sparql if "wdt%3AP99999" in u]
    assert len(data_queries) == 1
    urls.clear()
    rows, _, prop = wikidata.fetch_localities(wikidata_router(urls=urls), retrieved_at="d", prop="P1")
    assert prop == "P1" and len(urls) == 1  # a pinned property skips discovery


# --- CSV / XLSX tables ---------------------------------------------------------------------------


def _xlsx(rows: list[list[object]]) -> bytes:
    """A minimal one-sheet XLSX (shared strings for text, plain numbers) built with zipfile."""
    import io
    import zipfile
    from xml.sax.saxutils import escape

    strings: list[str] = []
    out = []
    for r, row in enumerate(rows, 1):
        cells = []
        for c, value in enumerate(row):
            ref = f"{chr(65 + c)}{r}"
            if isinstance(value, str):
                strings.append(value)
                cells.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
            else:
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
        out.append(f'<row r="{r}">{"".join(cells)}</row>')
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet = f'<worksheet xmlns="{ns}"><sheetData>{"".join(out)}</sheetData></worksheet>'
    sst = f'<sst xmlns="{ns}">' + "".join(f"<si><t>{escape(s)}</t></si>" for s in strings) + "</sst>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
        zf.writestr("xl/sharedStrings.xml", sst)
    return buf.getvalue()


CBS_ROWS = [
    ["קובץ יישובים 2023"],  # a title above the table
    ["שם יישוב", "סמל יישוב", "שם יישוב באנגלית", "נפה", "קואורדינטה X", "קואורדינטה Y"],
    ["תל אביב -יפו", 5000, "TEL AVIV - YAFO", "תל אביב", 179490, 664000],
    ["ירושלים", 3000, "JERUSALEM", "ירושלים", "", ""],  # no coordinates in this row
]


def test_xlsx_with_itm_columns_gives_localities() -> None:
    records = tables.read_records(_xlsx(CBS_ROWS))
    assert len(records) == 2 and "קואורדינטה X" in records[0]
    rows, skipped = localities_from_records(records, source="s", retrieved_at="d")
    assert [r.code for r in rows] == ["5000"]
    assert abs(rows[0].lat - 32.06856625) < 1e-5 and rows[0].name_en == "TEL AVIV - YAFO"
    assert skipped["no_coordinates"] == 1


def test_csv_in_utf8_and_windows_1255_and_semicolons() -> None:
    text = "שם יישוב;סמל יישוב;X;Y\nתל אביב -יפו;5000;179490;664000\n"
    for data in (text.encode("utf-8-sig"), text.encode("cp1255")):
        records = tables.read_records(data)
        assert records and records[0]["סמל יישוב"] == "5000"
    assert tables.read_records(b"just,some,numbers\n1,2,3\n") == []


def test_html_and_xls_are_refused_with_a_reason() -> None:
    with pytest.raises(tables.UnsupportedFile, match="HTML"):
        tables.read_records(b"<!DOCTYPE html><html><body>ERROR</body></html>")
    with pytest.raises(tables.UnsupportedFile, match="XLS"):
        tables.read_records(b"\xd0\xcf\x11\xe0 rest of an old xls")


# --- CKAN resources: the file before the datastore --------------------------------------------------


def ckan_package(name: str, resources: list[dict]) -> dict:
    return {"result": {"name": name, "resources": resources}}


PACKAGES = {
    "localities-in-israel": ckan_package(
        "localities-in-israel",
        [
            {"id": "r-cbs", "name": "קובץ היישובים 2023", "format": "XLSX",
             "url": "https://data.gov.il/dataset/x/resource/r-cbs/download/yishuvim.xlsx",
             "datastore_active": False},
            {"id": "r-pdf", "name": "הסבר", "format": "PDF", "url": "https://x/y.pdf", "datastore_active": False},
        ],
    ),
    "citiesandsettelments": ckan_package(
        "citiesandsettelments",
        [{"id": "r-list", "name": "רשימת ישובים בישראל - מתעדכן", "format": "CSV", "url": "", "datastore_active": True}],
    ),
}  # fmt: skip


def package_fetch(url: str):
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if "package_show" in url:
        pkg = PACKAGES.get(query["id"][0])
        if pkg is None:
            raise HttpFailure(404, "HTTP 404")
        return pkg
    if "package_search" in url:
        return {"result": {"results": []}}
    raise HttpFailure(403, "HTTP 403 (datastore refused)")


def test_resource_candidates_rank_the_cbs_file_first_and_skip_non_tables() -> None:
    found = ckan.resource_candidates(fetch=package_fetch)
    assert [c["id"] for c in found] == ["r-cbs", "r-list"]
    assert found[0]["url"].endswith("yishuvim.xlsx") and found[0]["format"] == "XLSX"
    assert found[1]["url"] == "" and found[1]["datastore_active"]


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location(
        "fetch_localities_script", REPO / "scripts" / "geo" / "fetch_localities.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _router(monkeypatch, script, *, files: dict[str, bytes] | None = None, ckan_ok=True):
    """Route the script's requests. CKAN metadata answers (package_show), the datastore is refused
    with 403 like the real site's firewall did, files answer from ``files``; Wikidata from the
    fixtures."""
    files = files or {}

    def fake_get_json(url: str, *, accept="application/json", timeout=60.0, log=None):
        host = urllib.parse.urlparse(url).netloc
        try:
            if host in ("query.wikidata.org", "www.wikidata.org"):
                payload, status = wikidata_router()(url), 200
            elif ckan_ok:
                payload, status = package_fetch(url), 200
            else:
                raise HttpFailure(403, "HTTP 403 Forbidden")
        except HttpFailure as exc:
            if log is not None:
                log.add(url, exc.status)
            raise
        if log is not None:
            log.add(url, status)
        return payload

    def fake_get_bytes(url: str, *, accept="*/*", timeout=120.0, max_bytes=0, log=None):
        if url in files:
            if log is not None:
                log.add(url, 200)
            return files[url]
        if log is not None:
            log.add(url, 403)
        raise HttpFailure(403, "HTTP 403 Forbidden")

    monkeypatch.setattr(script, "get_json", fake_get_json)
    monkeypatch.setattr(script, "get_bytes", fake_get_bytes)


CBS_URL = "https://data.gov.il/dataset/x/resource/r-cbs/download/yishuvim.xlsx"


def test_script_reads_the_resource_file_when_the_datastore_is_refused(
    script, monkeypatch, tmp_path, capsys
) -> None:
    _router(monkeypatch, script, files={CBS_URL: _xlsx(CBS_ROWS)})
    out = tmp_path / "localities.csv"
    rc = script.main(["--out", str(out), "--needed-from", "none"])
    stdout = capsys.readouterr().out
    assert rc == 0
    assert "SOURCE data.gov.il CKAN: " in stdout and "ckan file r-cbs: 2 records, 1 with coordinates" in stdout
    assert "ckan datastore r-list: HttpFailure: HTTP 403" in stdout  # tried, refused, reported
    table = load_localities(out)
    assert table["5000"].source == "data.gov.il resource r-cbs (file)"  # the CBS file wins over Wikidata
    assert table["3000"].source == "wikidata" and table["874"].source == "wikidata"


def test_script_survives_everything_from_ckan_failing_and_uses_wikidata(
    script, monkeypatch, tmp_path, capsys
) -> None:
    _router(monkeypatch, script, ckan_ok=False)
    out = tmp_path / "localities.csv"
    rc = script.main(["--out", str(out), "--needed-from", "none"])
    stdout = capsys.readouterr().out
    assert rc == 0
    assert "SOURCE data.gov.il CKAN: HTTP 403" in stdout and "rows=0" in stdout
    assert "SOURCE Wikidata SPARQL: " in stdout and "rows=4" in stdout
    assert "wikidata property: P99999 (signature" in stdout
    table = load_localities(out)
    assert sorted(table) == ["3000", "4000", "5000", "874"]
    assert {loc.source for loc in table.values()} == {"wikidata"}


def test_script_fails_clearly_when_every_source_returns_nothing(
    script, monkeypatch, tmp_path, capsys
) -> None:
    def nothing(url: str, **kw):
        if kw.get("log") is not None:
            kw["log"].add(url, 403)
        raise HttpFailure(403, "HTTP 403 Forbidden")

    monkeypatch.setattr(script, "get_json", nothing)
    monkeypatch.setattr(script, "get_bytes", nothing)
    out = tmp_path / "localities.csv"
    rc = script.main(["--out", str(out), "--needed-from", "none"])
    stdout = capsys.readouterr().out
    assert rc == 1
    assert "::error::no source returned any locality row" in stdout
    assert "SOURCE data.gov.il CKAN: HTTP 403" in stdout and "SOURCE Wikidata SPARQL: HTTP 403" in stdout
    assert not out.exists()
