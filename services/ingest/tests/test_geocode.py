"""Store coordinates (docs/geocoding.md): ITM conversion, the locality table, the Nominatim client's
politeness and cache, the address geocoder's city check and fallback order, the resolver.

No network and no database: Nominatim and data.gov.il are replaced by fakes.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from smartcart_ingest.geocode import ckan, sources
from smartcart_ingest.geocode.itm import in_israel, itm_to_wgs84
from smartcart_ingest.geocode.localities import (
    Locality,
    centroid_from_nominatim,
    classify_fields,
    detect_columns,
    load_localities,
    localities_from_records,
    names_from_records,
    names_match,
    normalize_code,
    normalize_name,
    write_localities,
)
from smartcart_ingest.geocode.nominatim import (
    Blocked,
    BudgetExhausted,
    MissingContact,
    NominatimClient,
    request_key,
)
from smartcart_ingest.geocode.resolve import (
    GeoIndex,
    StoreGeocode,
    load_store_geocodes,
    write_store_geocodes,
)
from smartcart_ingest.geocode.stores import (
    StoreInput,
    build_queries,
    city_in_text,
    clean_address,
    geocode_stores,
    infer_by_name,
    judge_result,
    pick_result,
)

REPO = Path(__file__).resolve().parents[3]
SAMPLE = REPO / "data" / "geo" / "localities_sample.csv"

# --- ITM -> WGS 84 -----------------------------------------------------------------------------

# Expected values computed with pyproj (EPSG:2039 -> EPSG:4326) when the test was written.
ITM_POINTS = [
    # (east, north, lat, lon, what)
    (219529.584, 626907.390, 31.73476304, 35.20521378, "the projection origin"),
    (179490.0, 664000.0, 32.06856625, 34.78117769, "central Tel Aviv"),
    (180000.0, 665000.0, 32.07760192, 34.78653770, "north Tel Aviv"),
    (190000.0, 382000.0, 29.52534735, 34.90058862, "near Eilat"),
    (250000.0, 780000.0, 33.11484390, 35.53169512, "the north, near Metula"),
    (160000.0, 590000.0, 31.40038212, 34.57927500, "the south-west"),
]


@pytest.mark.parametrize(("east", "north", "lat", "lon", "what"), ITM_POINTS, ids=lambda v: str(v))
def test_itm_conversion_matches_pyproj_within_a_metre(east, north, lat, lon, what) -> None:
    got_lat, got_lon = itm_to_wgs84(east, north)
    assert abs(got_lat - lat) < 1e-5, what  # 1e-5 degrees of latitude is about 1.1 m
    assert abs(got_lon - lon) < 1.2e-5, what


def test_itm_conversion_lands_on_known_cities() -> None:
    """ITM values of city centres (the first is the ITM of the Tel Aviv centre used above)."""
    lat, lon = itm_to_wgs84(179556.03, 665855.39)  # ITM of 32.0853 N, 34.7818 E (pyproj, inverse)
    assert (round(lat, 4), round(lon, 4)) == (32.0853, 34.7818)
    lat, lon = itm_to_wgs84(220333.46, 630626.13)  # Jerusalem, 31.7683 N, 35.2137 E
    assert (round(lat, 4), round(lon, 4)) == (31.7683, 35.2137)


def test_in_israel_bounds() -> None:
    assert in_israel(32.08, 34.78)
    assert not in_israel(0.0, 0.0)
    assert not in_israel(51.5, -0.1)  # London


# --- the locality table ------------------------------------------------------------------------


def test_normalize_code() -> None:
    assert normalize_code(" 0874 ") == "874"
    assert normalize_code(5000) == "5000"
    assert normalize_code("5000.0") == "5000"
    for unknown in ("0", "00", "", None, "abc", " "):
        assert normalize_code(unknown) is None


def test_name_matching_ignores_quotes_hyphens_and_kiryat_spelling() -> None:
    assert normalize_name("קריית  שמונה") == normalize_name("קרית שמונה")
    assert names_match("תל אביב -יפו", "תל אביב-יפו")
    assert names_match("תל אביב -יפו", "תל־אביב–יפו")  # OSM: Hebrew maqaf and an en dash
    assert names_match("מודיעין-מכבים-רעות", "מודיעין־מכבים־רעות")
    assert names_match("תל אביב", "תל אביב-יפו")  # the short name is a leading part
    assert names_match("ראשון לציון", "ראשון לציון")
    assert not names_match("רמת גן", "גן")  # a trailing fragment is not a match
    assert not names_match("אשדוד", "אשקלון")
    assert not names_match("", "אשדוד")


CKAN_ITM = [
    {"_id": 1, "סמל_ישוב": 5000, "שם_ישוב": "תל אביב -יפו", "X": 179490, "Y": 664000},
    {"_id": 2, "סמל_ישוב": "0874", "שם_ישוב": "מגדל העמק", "X": 0, "Y": 0},  # no usable point
    {"_id": 3, "סמל_ישוב": 9999, "שם_ישוב": "בלי נקודה", "X": None, "Y": None},
    {"_id": 4, "סמל_ישוב": 0, "שם_ישוב": "לא ישוב", "X": 1, "Y": 1},
    {"_id": 5, "סמל_ישוב": 7777, "שם_ישוב": "", "X": 179490, "Y": 664000},
    {"_id": 6, "סמל_ישוב": 8888, "שם_ישוב": "רחוק", "X": 5, "Y": 5},  # converts outside Israel
]


def test_localities_from_ckan_records_converts_itm_and_counts_what_it_drops() -> None:
    rows, skipped = localities_from_records(CKAN_ITM, source="test", retrieved_at="2026-10-08")
    assert [r.code for r in rows] == ["5000"]
    tel_aviv = rows[0]
    assert tel_aviv.name_he == "תל אביב -יפו"
    assert abs(tel_aviv.lat - 32.06856625) < 1e-5 and abs(tel_aviv.lon - 34.78117769) < 1.2e-5
    assert skipped == {"no_code": 1, "no_name": 1, "no_coordinates": 2, "outside_israel": 1}


def test_localities_from_records_with_wgs84_columns() -> None:
    rows, _ = localities_from_records(
        [{"code": "3000", "name": "ירושלים", "latitude": "31.77", "longitude": "35.21"}],
        source="s",
        retrieved_at="d",
    )
    assert (rows[0].code, rows[0].lat, rows[0].lon) == ("3000", 31.77, 35.21)


def test_column_detection_and_classification() -> None:
    names_only = ["_id", "סמל_ישוב", "שם_ישוב", "שם_נפה"]
    assert classify_fields(names_only) == "names"
    assert classify_fields([*names_only, "X", "Y"]) == "coords"
    assert classify_fields(["שם_נפה", "סמל_נפה"]) is None
    assert detect_columns(["סמל_ישוב", "שם_ישוב"]) == {"code": "סמל_ישוב", "name_he": "שם_ישוב"}
    assert names_from_records(CKAN_ITM)["5000"] == ("תל אביב -יפו", "")


def test_localities_csv_round_trip_and_bad_rows(tmp_path: Path) -> None:
    path = tmp_path / "l.csv"
    rows = [Locality("874", "מגדל העמק", "Migdal HaEmek", 32.68, 35.24, "s", "2026-10-08")]
    assert write_localities(path, rows) == 1
    assert load_localities(path)["874"].name_he == "מגדל העמק"
    path.write_text(
        path.read_text(encoding="utf-8") + "5,מחוץ,,10.0,10.0,s,d\n6,בלי,,x,y,s,d\n",
        encoding="utf-8",
    )
    assert set(load_localities(path)) == {"874"}  # outside Israel and non-numeric rows ignored
    assert load_localities(tmp_path / "missing.csv") == {}


def test_committed_sample_is_marked_sample_and_inside_israel() -> None:
    table = load_localities(SAMPLE)
    assert len(table) >= 20
    assert all("SAMPLE" in loc.source for loc in table.values())
    assert table["5000"].name_he.startswith("תל אביב")


def test_committed_full_table_is_empty_or_has_no_sample_rows() -> None:
    """data/geo/localities.csv is only ever written by fetch_localities.py."""
    full = load_localities(REPO / "data" / "geo" / "localities.csv")
    assert all("SAMPLE" not in loc.source for loc in full.values())


# --- data.gov.il (CKAN) ------------------------------------------------------------------------


def _fake_ckan(pages: dict[str, dict]) -> object:
    calls: list[str] = []

    def fetch(url: str):
        calls.append(url)
        for needle, payload in pages.items():
            if needle in url:
                return payload
        raise OSError(f"no fake for {url}")

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def test_ckan_datastore_pages_until_total() -> None:
    page = [{"i": n} for n in range(ckan.PAGE)]
    seen = []

    def fetch(url: str):
        seen.append(url)
        if "offset=0" in url:
            return {"result": {"records": page, "total": ckan.PAGE + 2}}
        return {"result": {"records": [{"i": -1}, {"i": -2}], "total": ckan.PAGE + 2}}

    out = list(ckan.datastore_records("rid", fetch=fetch))
    assert len(out) == ckan.PAGE + 2 and len(seen) == 2


def test_ckan_discover_prefers_resources_with_coordinates() -> None:
    def fetch(url: str):
        if "package_search" in url:
            return {
                "result": {
                    "results": [
                        {
                            "name": "pkg",
                            "resources": [
                                {"id": "names", "datastore_active": True, "name": "n"},
                                {"id": "coords", "datastore_active": True, "name": "c"},
                                {"id": "file", "datastore_active": False, "name": "f"},
                            ],
                        }
                    ]
                }
            }
        fields = {
            "names": ["_id", "סמל_ישוב", "שם_ישוב"],
            "coords": ["_id", "סמל_ישוב", "שם_ישוב", "X", "Y"],
        }
        rid = "names" if "resource_id=names" in url else "coords"
        return {"result": {"fields": [{"id": f} for f in fields[rid]], "records": []}}

    found = ckan.discover(("q",), fetch=fetch)
    assert [(r["id"], r["kind"]) for r in found] == [("coords", "coords"), ("names", "names")]


# --- the Nominatim client ----------------------------------------------------------------------


class FakeNominatim:
    """Canned answers by substring of the query; records every request."""

    def __init__(self, answers: dict[str, list[dict]] | None = None) -> None:
        self.answers = answers or {}
        self.urls: list[str] = []
        self.headers: list[dict] = []

    def __call__(self, url: str, headers, timeout):
        import urllib.parse

        self.urls.append(url)
        self.headers.append(dict(headers))
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]
        for needle, result in self.answers.items():
            if needle in q:
                return result
        return []


class Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _client(
    tmp_path: Path, fake: FakeNominatim, clock: Clock | None = None, **kw
) -> NominatimClient:
    clock = clock or Clock()
    return NominatimClient(
        tmp_path / "cache.jsonl",
        contact="ops@example.org",
        fetch=fake,
        sleep=clock.sleep,
        clock=clock.time,
        **kw,
    )


def test_client_requires_a_contact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOMINATIM_CONTACT", raising=False)
    with pytest.raises(MissingContact):
        NominatimClient(tmp_path / "c.jsonl", fetch=FakeNominatim())
    monkeypatch.setenv("NOMINATIM_CONTACT", "me@example.org")
    client = NominatimClient(tmp_path / "c.jsonl", fetch=FakeNominatim())
    assert "me@example.org" in client.user_agent and "SmartCart" in client.user_agent


def test_client_sends_the_policy_headers_and_restricts_to_israel(tmp_path: Path) -> None:
    fake = FakeNominatim()
    client = _client(tmp_path, fake)
    client.search("האיצטדיון 11, מגדל העמק")
    assert "ops@example.org" in fake.headers[0]["User-Agent"]
    assert "countrycodes=il" in fake.urls[0] and "addressdetails=1" in fake.urls[0]


def test_client_never_exceeds_one_request_per_second(tmp_path: Path) -> None:
    clock = Clock()
    client = _client(tmp_path, FakeNominatim(), clock, min_interval=0.1)  # clamped up to 1 s
    for n in range(4):
        client.search(f"query {n}")
    assert client.requests_made == 4
    assert len(clock.sleeps) == 3 and all(abs(s - 1.0) < 1e-9 for s in clock.sleeps)


def test_the_same_query_is_never_requested_twice_even_across_runs(tmp_path: Path) -> None:
    fake = FakeNominatim({"אשדוד": [{"lat": "31.8", "lon": "34.65", "address": {"city": "אשדוד"}}]})
    first = _client(tmp_path, fake)
    results, key, cached = first.search("בן גוריון 1,  אשדוד")
    assert not cached and results[0]["lat"] == "31.8"
    again, key2, cached2 = first.search("בן גוריון 1, אשדוד")  # whitespace differs only
    assert cached2 and key2 == key and again == results
    nothing, _, _ = first.search("אין כזה 1, חיפה")
    assert nothing == []
    second = _client(tmp_path, fake)  # a new process: the cache file is read back
    assert second.search("בן גוריון 1, אשדוד")[2] is True
    assert second.search("אין כזה 1, חיפה")[2] is True  # an empty answer is cached too
    assert len(fake.urls) == 2 and second.requests_made == 0 and second.cache_hits == 2


def test_budget_blocks_and_errors(tmp_path: Path) -> None:
    client = _client(tmp_path, FakeNominatim(), max_requests=1)
    client.search("a")
    with pytest.raises(BudgetExhausted):
        client.search("b")
    client.search("a")  # a cached query costs nothing, even with the budget spent

    def blocked(url, headers, timeout):
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)  # type: ignore[arg-type]

    stopped = NominatimClient(
        tmp_path / "b.jsonl", contact="x@y.z", fetch=blocked, sleep=lambda s: None
    )
    with pytest.raises(Blocked):
        stopped.search("a")
    assert not (tmp_path / "b.jsonl").exists()  # a failure is not cached


def test_request_key_ignores_whitespace_but_not_parameters() -> None:
    assert request_key("a  b", {"x": "1"}) == request_key("a b", {"x": "1"})
    assert request_key("a b", {"x": "1"}) != request_key("a b", {"x": "2"})


# --- queries and the city check ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("האיצטדיון 11", ("האיצטדיון 11", True)),
        ("האומן,15", ("האומן 15", True)),
        ("אבן גבירול157", ("אבן גבירול 157", True)),
        ("20 נחל פרת", ("נחל פרת 20", True)),
        ("46-50 פנקס", ("פנקס 46", True)),
        ("רחוב המפוח 11, אזור התעשיה", ("המפוח 11", True)),
        ("רח' המלאכה 32", ("המלאכה 32", True)),
        ("הסתת 15 א תעשיה", ("הסתת 15", True)),
        ('הר"ן 6 פינת פנים המאירים', ('הר"ן 6', True)),
        ("שד' הנשיא 3", ("שדרות הנשיא 3", True)),
        ("שרפה 22, כביש ראשי של העיר 0", ("שרפה 22", True)),
        ("שדרות ירושלים פינת נופי חמד", ("שדרות ירושלים", False)),
        ("ואדי אלפש, כביש 672 0", ("ואדי אלפש", False)),
        ("מרכז מסחרי", ("מרכז מסחרי", False)),
        ("ת.ד. 123", ("", False)),
        ("123", ("", False)),
        (None, ("", False)),
        ("", ("", False)),
    ],
)
def test_clean_address(raw, expected) -> None:
    assert clean_address(raw) == expected


def test_build_queries_asks_for_the_house_then_the_street() -> None:
    assert build_queries("בן ציון גליס 30", "פתח תקווה") == [
        ("address", "בן ציון גליס 30, פתח תקווה"),
        ("street", "בן ציון גליס, פתח תקווה"),
    ]
    assert build_queries("שדרות ירושלים", "רמלה") == [("street", "שדרות ירושלים, רמלה")]
    assert build_queries("", "רמלה") == [] and build_queries("רחוב 1", "") == []


def hit(
    city: str,
    *,
    road="האיצטדיון",
    house="11",
    lat="32.678",
    lon="35.239",
    category="building",
    **extra,
):
    address = {
        "road": road,
        "city": city,
        "country_code": "il",
        **({"house_number": house} if house else {}),
    }
    return {
        "lat": lat,
        "lon": lon,
        "category": category,
        "type": "yes",
        "address": address,
        **extra,
    }


def test_a_result_is_kept_only_in_the_stores_own_city() -> None:
    assert judge_result(hit("מגדל העמק"), "מגדל העמק") == (32.678, 35.239, "address")
    assert judge_result(hit("נוף הגליל"), "מגדל העמק") is None  # same street name, other city
    assert judge_result(hit("תל אביב-יפו"), "תל אביב -יפו") is not None


def test_street_and_locality_level_results() -> None:
    street = hit("מגדל העמק", house=None, category="highway")
    assert judge_result(street, "מגדל העמק") == (32.678, 35.239, "street")
    only_the_city = {"lat": "32.68", "lon": "35.24", "category": "boundary", "type": "administrative",
                     "address": {"city": "מגדל העמק", "country_code": "il"}}  # fmt: skip
    assert judge_result(only_the_city, "מגדל העמק") is None
    outside = hit("מגדל העמק", lat="48.0", lon="2.0")
    assert judge_result(outside, "מגדל העמק") is None
    abroad = hit("מגדל העמק")
    abroad["address"]["country_code"] = "ps"
    assert judge_result(abroad, "מגדל העמק") is None


def test_an_address_beats_a_street() -> None:
    street = hit("חיפה", house=None, category="highway", lat="32.1", lon="34.9")
    house = hit("חיפה", lat="32.2", lon="34.95")
    assert pick_result([street, house], "חיפה") == (32.2, 34.95, "address")
    assert pick_result([hit("עכו")], "חיפה") is None


# --- the geocoding run: fallback order ---------------------------------------------------------

LOCALITIES = {
    "874": Locality("874", "מגדל העמק", "", 32.68, 35.24, "t", "d"),
    "7900": Locality("7900", "פתח תקווה", "", 32.09, 34.89, "t", "d"),
    "2710": Locality("2710", "אום אלפחם", "", 32.52, 35.15, "t", "d"),
}


def S(code: str, name: str, address: str | None, city: str | None, chain: str = "c1") -> StoreInput:
    return StoreInput(chain, code, name, address, city)


def test_run_prefers_address_then_street_then_leaves_the_locality_to_the_loader(
    tmp_path: Path,
) -> None:
    fake = FakeNominatim(
        {
            "האיצטדיון 11, מגדל העמק": [hit("מגדל העמק")],
            # store 2: the house number is unknown to OSM, the street query finds the street
            "בן ציון גליס, פתח תקווה": [
                hit(
                    "פתח תקווה",
                    road="בן ציון גליס",
                    house=None,
                    category="highway",
                    lat="32.1",
                    lon="34.88",
                )
            ],
            # store 3: the only hit is in another city
            "שרפה 22, אום אלפחם": [hit("חיפה", road="שרפה", house="22")],
        }
    )
    client = _client(tmp_path, fake)
    stores = [
        S("1", "אושר עד", "האיצטדיון 11", "874"),
        S("2", 'פ"ת', "בן ציון גליס 30", "7900"),
        S("3", "אום", "שרפה 22, כביש ראשי של העיר 0", "2710"),
    ]
    rows, stats = geocode_stores(stores, LOCALITIES, client)
    by_code = {r.store_code: r for r in rows}
    assert by_code["1"].precision == "address" and by_code["1"].source == "nominatim"
    assert by_code["2"].precision == "street" and (by_code["2"].lat, by_code["2"].lon) == (
        32.1,
        34.88,
    )
    assert "3" not in by_code and stats.no_match == 1
    assert dict(stats.by_precision) == {"address": 1, "street": 1}
    assert len(by_code["1"].query_hash) == 16 and by_code["1"].geocoded_at.endswith("Z")
    # Order of requests: store 1 one query, store 2 two queries, store 3 two queries
    assert len(fake.urls) == 5

    # The loader's fallback order, on the resulting rows: geocode row, then locality, then nothing.
    index = GeoIndex(LOCALITIES, {(r.chain_id, r.store_code): r for r in rows})
    assert index.resolve("c1", "1", "874").precision == "address"
    assert index.resolve("c1", "2", "7900").precision == "street"
    assert index.resolve("c1", "3", "2710").precision == "locality"
    assert index.resolve("c1", "4", "0") is None
    assert index.resolve("c1", "5", None) is None
    assert index.resolve("c1", "6", "123456") is None  # a code the table does not have


def test_run_does_not_repeat_requests_or_rows(tmp_path: Path) -> None:
    fake = FakeNominatim({"האיצטדיון 11, מגדל העמק": [hit("מגדל העמק")]})
    stores = [S("1", "אושר עד", "האיצטדיון 11", "874")]
    rows, _ = geocode_stores(stores, LOCALITIES, _client(tmp_path, fake))
    assert len(fake.urls) == 1
    existing = {(r.chain_id, r.store_code): r for r in rows}
    # same run again with the rows: nothing is even looked up
    again, stats = geocode_stores(stores, LOCALITIES, _client(tmp_path, fake), existing=existing)
    assert again == [] and stats.skipped_existing == 1 and len(fake.urls) == 1
    # rows lost but the cache kept: the client answers from the cache, still no request
    lost, _ = geocode_stores(stores, LOCALITIES, _client(tmp_path, fake))
    assert len(lost) == 1 and len(fake.urls) == 1


def test_run_stops_at_max_stores_and_when_blocked(tmp_path: Path) -> None:
    fake = FakeNominatim()
    stores = [S(str(n), "x", f"הרצל {n}", "874") for n in range(1, 6)]
    rows, stats = geocode_stores(stores, LOCALITIES, _client(tmp_path, fake), max_stores=2)
    assert stats.attempted == 2 and "max_stores" in stats.stopped and rows == []

    def blocked(url, headers, timeout):
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)  # type: ignore[arg-type]

    client = NominatimClient(
        tmp_path / "x.jsonl", contact="a@b.c", fetch=blocked, sleep=lambda s: None
    )
    _, stats = geocode_stores(stores, LOCALITIES, client)
    assert "403" in stats.stopped and stats.attempted == 0


def test_unknown_city_falls_back_to_an_exact_name_match_when_the_text_gives_nothing(
    tmp_path: Path,
) -> None:
    fake = FakeNominatim()  # answers nothing
    stores = [
        S("1", "אום אלפחם", "שרפה 22", "0"),  # the store is named after the locality
        S("2", "יוחננוף מפוח", "רחוב המפוח 11", "0"),
        S("3", "x", "רחוב 1", None),
        S("4", "x", "", "99999"),  # a code the table does not have, and no address
    ]
    rows, stats = geocode_stores(stores, LOCALITIES, _client(tmp_path, fake))
    assert [(r.store_code, r.precision, r.source) for r in rows] == [
        ("1", "locality", "cbs-name-match")
    ]
    assert (rows[0].lat, rows[0].lon) == (32.52, 35.15)
    assert stats.unknown_city_code == 3 and stats.no_city == 1
    assert (
        stats.no_match == 2 and stats.skipped_online_or_no_address == 2
    )  # "רחוב 1" has no street name
    assert infer_by_name(S("9", "תל אביב", None, "0"), LOCALITIES) is None


def test_city_in_text_matches_whole_words_and_hyphenated_parts() -> None:
    assert city_in_text("תל אביב-יפו", "קרפור סיטי תל אביב")
    assert city_in_text("יפו", "דיל יפו")
    assert city_in_text("בת ים", "קרפור סיטי עוזיאל בת ים")
    assert not city_in_text("לוד", "קלודין 5")  # not a whole word
    assert not city_in_text("חיפה", "ברחוב הרצל")
    assert not city_in_text(None, "חיפה")


def test_unknown_city_is_geocoded_from_the_city_in_its_own_text(tmp_path: Path) -> None:
    fake = FakeNominatim(
        {
            # the address alone is ambiguous: the first hit is in another city, the second is in the text
            "הנשיא 1": [
                hit("חיפה", road="הנשיא", house="1", lat="32.8", lon="35.0"),
                hit("פרדסיה", road="הנשיא", house="1", lat="32.30", lon="34.91"),
            ],
            "ואדי אלפש": [hit("חיפה", road="ואדי אלפש", house=None, category="highway")],
        }
    )
    stores = [
        S("1", "שלי פרדסיה- הנשיא", "הנשיא 1 צ.פרדסיה", "0"),
        S(
            "2", "דליית אל כרמל", "ואדי אלפש, כביש 672 0", "0"
        ),  # the only hit is in a city not in its text
    ]
    rows, stats = geocode_stores(stores, LOCALITIES, _client(tmp_path, fake))
    by_code = {r.store_code: r for r in rows}
    assert (by_code["1"].precision, by_code["1"].source) == ("address", "nominatim:city-from-text")
    assert (by_code["1"].lat, by_code["1"].lon) == (
        32.30,
        34.91,
    )  # the city in the store's text wins
    assert "2" not in by_code and stats.no_match == 1
    assert dict(stats.by_source) == {"nominatim:city-from-text": 1}
    assert all("limit=10" in u and "countrycodes=il" in u for u in fake.urls)


def test_text_geocoding_also_serves_a_code_missing_from_the_table(tmp_path: Path) -> None:
    fake = FakeNominatim(
        {"הרצל 5": [hit("בית שאן", road="הרצל", house="5", lat="32.5", lon="35.5")]}
    )
    rows, stats = geocode_stores(
        [S("1", "דיל בית שאן", "הרצל 5", "9200")], LOCALITIES, _client(tmp_path, fake)
    )
    assert [(r.precision, r.source) for r in rows] == [("address", "nominatim:city-from-text")]
    assert stats.no_city == 1 and stats.unknown_city_code == 0


def test_store_geocodes_csv_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "store_geocodes.csv"
    rows = [
        StoreGeocode(
            "7290058140886", "10", 32.1, 34.9, "address", "nominatim", "abc", "2026-10-08T00:00:00Z"
        ),
        StoreGeocode("7290027600007", "2", 32.2, 34.8, "locality", "cbs-name-match"),
    ]
    assert write_store_geocodes(path, rows) == 2
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert header == "chain_id,store_code,lat,lon,precision,source,query_hash,geocoded_at"
    loaded = load_store_geocodes(path)
    assert loaded[("7290058140886", "10")].precision == "address"
    path.write_text(
        path.read_text(encoding="utf-8") + "c,1,32,34,bogus,s,,\nc,2,0,0,address,s,,\n",
        encoding="utf-8",
    )
    assert set(load_store_geocodes(path)) == {("7290058140886", "10"), ("7290027600007", "2")}


def test_centroid_from_nominatim_accepts_only_a_matching_settlement(tmp_path: Path) -> None:
    fake = FakeNominatim(
        {
            "כרמיאל": [
                {
                    "lat": "32.9",
                    "lon": "35.3",
                    "category": "highway",
                    "type": "residential",
                    "name": "כרמיאל",
                },
                {
                    "lat": "32.91",
                    "lon": "35.30",
                    "category": "place",
                    "type": "city",
                    "name": "כרמיאל",
                },
            ],
            "אחר": [
                {
                    "lat": "32.9",
                    "lon": "35.3",
                    "category": "place",
                    "type": "city",
                    "name": "משהו אחר",
                }
            ],
        }
    )
    client = _client(tmp_path, fake)
    lat, lon, _ = centroid_from_nominatim(client, "כרמיאל")
    assert (lat, lon) == (32.91, 35.30)
    assert centroid_from_nominatim(client, "אחר") is None


# --- the real Stores fixtures ------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_stores() -> list[StoreInput]:
    found = sources.stores_from_fixtures()
    if not found:
        pytest.skip("no real Stores fixtures")
    return found


def test_real_fixture_stores_are_physical_and_carry_a_numeric_city(real_stores) -> None:
    assert len(real_stores) >= 800
    assert {s.chain_id for s in real_stores} >= {"7290027600007", "7290058140886"}
    with_city = [s for s in real_stores if normalize_code(s.city)]
    assert len(with_city) > 700
    assert sum(1 for s in real_stores if not normalize_code(s.city)) >= 50  # the city-0 stores


def test_sample_table_places_the_big_city_stores_at_locality_precision(real_stores) -> None:
    index = GeoIndex(load_localities(SAMPLE), {})
    cov = sources.coverage(real_stores, index)
    assert cov["address"] == 0 and cov["street"] == 0
    assert cov["locality"] > 300  # Tel Aviv, Jerusalem, Haifa, Petah Tikva, Beer Sheva, ...
    assert cov["locality"] + cov["none"] == len(real_stores)
    tel_aviv = [s for s in real_stores if s.city == "5000"]
    assert tel_aviv and all(index.resolve(s.chain_id, s.store_code, s.city) for s in tel_aviv)


def test_sample_cities_are_the_cities_the_stores_name(real_stores) -> None:
    """Cross-check of the sample's codes against the data itself: where a real store is named
    exactly after its city, the sample's name for that code must be the same city."""
    table = load_localities(SAMPLE)
    checked = 0
    for s in real_stores:
        loc = table.get(normalize_code(s.city) or "")
        if loc and normalize_name(s.name) and normalize_name(s.name) == normalize_name(loc.name_he):
            checked += 1
    assert checked >= 5
    for s in real_stores:
        loc = table.get(normalize_code(s.city) or "")
        if loc is None:
            continue
        # a store whose whole name is another sample locality's name contradicts the code
        for other in table.values():
            if other.code != loc.code and normalize_name(s.name) == normalize_name(other.name_he):
                pytest.fail(
                    f"{s.chain_id}/{s.store_code} {s.name!r} has city {s.city} ({loc.name_he})"
                )


def test_json_cache_lines_are_valid_json(tmp_path: Path) -> None:
    client = _client(
        tmp_path, FakeNominatim({"x": [{"lat": "32", "lon": "34", "extra": 1, "type": "t"}]})
    )
    client.search("x")
    line = json.loads((tmp_path / "cache.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert line["query"] == "x" and line["results"] == [{"lat": "32", "lon": "34", "type": "t"}]
