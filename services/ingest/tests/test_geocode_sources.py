"""The locality sources: the HTTP helper's User-Agent, the Wikidata parser and the fetch script's
per-source report, preference order and failure exit code. No network."""

from __future__ import annotations

import importlib.util
import json
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from smartcart_ingest.geocode import http, wikidata
from smartcart_ingest.geocode.http import HttpFailure, StatusLog, get_json
from smartcart_ingest.geocode.localities import load_localities

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


def test_fetch_localities_runs_discovery_then_one_data_query() -> None:
    urls: list[str] = []

    def fetch(url: str):
        urls.append(url)
        return PROPERTY if len(urls) == 1 else LOCALITIES

    rows, _skipped, prop = wikidata.fetch_localities(fetch, retrieved_at="d")
    assert prop == "P99999" and len(rows) == 4 and len(urls) == 2
    urls.clear()
    rows, _, prop = wikidata.fetch_localities(fetch, retrieved_at="d", prop="P1")
    assert prop == "P1" and len(urls) == 1  # a pinned property skips discovery


# --- the fetch script --------------------------------------------------------------------------


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location(
        "fetch_localities_script", REPO / "scripts" / "geo" / "fetch_localities.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _router(monkeypatch, script, *, ckan):
    """Route the script's requests: ``ckan`` is a payload fn or an HttpFailure to raise."""

    def fake_get_json(url: str, *, accept="application/json", timeout=60.0, log=None):
        host = urllib.parse.urlparse(url).netloc
        if host == "query.wikidata.org":
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["query"][0]
            payload = PROPERTY if "wikibase:Property" in query else LOCALITIES
            status = 200
        else:
            status, payload = (ckan if isinstance(ckan, tuple) else (200, ckan))
        if log is not None:
            log.add(url, status)
        if status >= 400:
            raise HttpFailure(status, f"HTTP {status} Forbidden")
        return payload

    monkeypatch.setattr(script, "get_json", fake_get_json)


def test_script_survives_a_403_from_ckan_and_uses_wikidata(script, monkeypatch, tmp_path, capsys):
    _router(monkeypatch, script, ckan=(403, None))
    out = tmp_path / "localities.csv"
    rc = script.main(["--out", str(out), "--needed-from", "none"])
    stdout = capsys.readouterr().out
    assert rc == 0
    assert "SOURCE data.gov.il CKAN: HTTP 403" in stdout and "rows=0" in stdout
    assert "SOURCE Wikidata SPARQL: HTTP 200 x2; rows=4" in stdout
    table = load_localities(out)
    assert sorted(table) == ["3000", "4000", "5000", "874"]
    assert {loc.source for loc in table.values()} == {"wikidata"}


def test_script_prefers_the_cbs_source_where_both_have_a_code(script, monkeypatch, tmp_path, capsys):
    ckan_payload = {
        "result": {
            "fields": [{"id": "סמל_ישוב"}, {"id": "שם_ישוב"}, {"id": "lat"}, {"id": "lon"}],
            "records": [
                {"סמל_ישוב": 5000, "שם_ישוב": "תל אביב -יפו", "lat": 32.0853, "lon": 34.7818}
            ],
            "total": 1,
        }
    }
    _router(monkeypatch, script, ckan=ckan_payload)
    out = tmp_path / "localities.csv"
    rc = script.main(["--out", str(out), "--needed-from", "none", "--resource-id", "rid"])
    assert rc == 0
    assert "SOURCE data.gov.il CKAN: HTTP 200" in capsys.readouterr().out
    table = load_localities(out)
    assert table["5000"].source.startswith("data.gov.il") and table["5000"].lat == 32.0853
    assert table["3000"].source == "wikidata"  # only Wikidata had Jerusalem


def test_script_fails_clearly_when_every_source_returns_nothing(script, monkeypatch, tmp_path, capsys):
    def nothing(url: str, **kw):
        if kw.get("log") is not None:
            kw["log"].add(url, 403)
        raise HttpFailure(403, "HTTP 403 Forbidden")

    monkeypatch.setattr(script, "get_json", nothing)
    out = tmp_path / "localities.csv"
    rc = script.main(["--out", str(out), "--needed-from", "none"])
    stdout = capsys.readouterr().out
    assert rc == 1
    assert "::error::no source returned any locality row" in stdout
    assert "SOURCE data.gov.il CKAN: HTTP 403" in stdout and "SOURCE Wikidata SPARQL: HTTP 403" in stdout
    assert not out.exists()
