"""What leaves the API: error bodies, logs, headers, CORS, and where a location can end up.

* an error response never carries SQL, a traceback, an exception message or what the caller posted;
* logs never carry a token, an e-mail address, a precise location or an image;
* every response has the hardening headers; the API's CORS allows the configured origins only,
  never with credentials;
* a location exists in the database only as the rounded neighborhood point of a consenting user.
"""

from __future__ import annotations

import io
import logging
import logging.config
import re
import uuid

import jwt
import psycopg
import pytest
from api_world import JWT_SECRET, make_token
from fastapi.testclient import TestClient

from smartcart_api.auth import User, rls_claims
from smartcart_api.logsafe import StripQuery, uvicorn_log_config
from smartcart_api.main import app
from smartcart_api.settings import get_settings

pytestmark = pytest.mark.db


def h(uid, **claims) -> dict:
    return {"Authorization": f"Bearer {make_token(uid, **claims)}"}


@pytest.fixture
def user(db) -> uuid.UUID:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    return uid


@pytest.fixture
def quiet_client(client) -> TestClient:
    """The same app and overrides, answering a 500 like production instead of re-raising."""
    return TestClient(app, raise_server_exceptions=False)


# --- error bodies ---------------------------------------------------------------------------------


def test_an_unexpected_error_is_a_fixed_500(quiet_client, monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError(
            "SELECT secret FROM auth.users WHERE token = 'hunter2' -- /srv/app.py line 9"
        )

    monkeypatch.setattr("smartcart_api.routes.search.hybrid_search", boom)
    r = quiet_client.get("/search", params={"q": "חלב"})
    assert r.status_code == 500
    assert r.json() == {"detail": "internal error"}
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "hunter2" not in r.text and "Traceback" not in r.text and "SELECT" not in r.text


def test_a_database_that_is_down_or_busy_is_a_503_without_details(
    quiet_client, monkeypatch
) -> None:
    from psycopg_pool import PoolTimeout

    for exc in (
        psycopg.OperationalError("connection to server at 10.1.2.3, port 5432 failed: password=x"),
        PoolTimeout("couldn't get a connection after 30.00 sec"),
        psycopg.InterfaceError("the connection is closed"),
    ):

        def boom(*args, _e=exc, **kwargs):
            raise _e

        monkeypatch.setattr("smartcart_api.routes.search.hybrid_search", boom)
        r = quiet_client.get("/search", params={"q": "חלב"})
        assert r.status_code == 503 and r.headers["retry-after"] == "5"
        assert r.json() == {"detail": "the service is busy, try again shortly"}
        assert "10.1.2.3" not in r.text and "password" not in r.text


def test_a_value_the_database_refuses_is_a_422_without_the_sql_error(client, user) -> None:
    # a canonical id that does not exist: a foreign key violation, whose Postgres message names the
    # constraint, the table and the key
    body = {"name": "x", "items": [{"canonical_id": 987654321, "input_text": "x"}]}
    r = client.post("/me/lists", json=body, headers=h(user))
    assert r.status_code == 422
    assert r.json() == {"detail": "a referenced record does not exist or a value is not allowed"}
    for word in ("foreign key", "constraint", "list_items", "violates", "DETAIL", "Key ("):
        assert word not in r.text


def test_validation_errors_do_not_echo_what_was_posted(client, user) -> None:
    secret = "hunter2-" + "s" * 40
    r = client.post(
        "/me/lists", json={"name": "x", "items": [], "password": secret}, headers=h(user)
    )
    assert r.status_code == 422
    assert secret not in r.text and '"input"' not in r.text and '"ctx"' not in r.text
    body = r.json()["detail"][0]
    assert set(body) == {"type", "loc", "msg"} and body["loc"] == ["body", "password"]
    r = client.post("/compare", json={"items": [{"canonical_id": "x" * 500, "quantity": 1}]})
    assert r.status_code == 422 and "x" * 100 not in r.text


def test_a_key_with_a_lone_surrogate_cannot_break_the_error_response(client) -> None:
    r = client.post(
        "/parse-list",
        content=b'{"text": "a", "\\ud800": 1}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_authentication_errors_do_not_say_why(client, user) -> None:
    for header in (None, "Bearer x", "Basic x", f"Bearer {make_token(user, secret='y' * 40)}"):
        r = client.get("/me/lists", headers={} if header is None else {"Authorization": header})
        assert r.status_code == 401
        assert set(r.json()) == {"detail"}
        assert r.json()["detail"] in (
            "sign in required",
            "invalid token",
            "expected a Bearer token",
        )


def test_404s_for_other_users_data_look_like_404s_for_missing_data(client, user) -> None:
    other = uuid.uuid4()
    mine = client.post("/me/lists", json={"name": "x", "items": []}, headers=h(user)).json()["id"]
    # (the other account does not exist in auth.users: any id gets the same answer)
    a = client.get(f"/me/lists/{mine}", headers=h(other))
    b = client.get(f"/me/lists/{mine + 1000}", headers=h(other))
    assert a.status_code == b.status_code == 404 and a.json() == b.json()


# --- logs ------------------------------------------------------------------------------------------


def test_access_log_lines_lose_their_query_string() -> None:
    f = StripQuery()
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        (
            "10.0.0.1:5000",
            "GET",
            "/stores/nearest?chain_id=x&lat=32.0712345&lon=34.7812345",
            "1.1",
            200,
        ),
        None,
    )
    assert f.filter(record) is True
    line = record.getMessage()
    assert "32.07" not in line and "34.78" not in line and "?" not in line
    assert '"GET /stores/nearest HTTP/1.1" 200' in line
    # a record that is not an access line is left alone
    other = logging.LogRecord("x", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    assert f.filter(other) and other.getMessage() == "hello world"


def test_the_uvicorn_config_installs_the_filter_on_the_access_logger() -> None:
    config = uvicorn_log_config()
    assert config["loggers"]["uvicorn.access"]["filters"] == ["strip_query"]
    saved = {
        name: (list(lg.handlers), list(lg.filters), lg.propagate, lg.level)
        for name in ("uvicorn", "uvicorn.access", "uvicorn.error")
        for lg in [logging.getLogger(name)]
    }
    try:
        logging.config.dictConfig(config)
        stream = io.StringIO()
        access = logging.getLogger("uvicorn.access")
        handler = logging.StreamHandler(stream)
        access.addHandler(handler)
        access.info(
            '%s - "%s %s HTTP/%s" %d',
            "1.2.3.4:5",
            "GET",
            "/items/barcode/729?lat=32.0712&lon=34.78",
            "1.1",
            200,
        )
        assert "lat=" not in stream.getvalue() and "/items/barcode/729" in stream.getvalue()
    finally:
        for name, (handlers, filters, propagate, level) in saved.items():
            lg = logging.getLogger(name)
            lg.handlers[:] = handlers
            lg.filters[:] = filters
            lg.propagate, lg.level = propagate, level


def test_the_database_session_gets_the_claims_the_policies_read_and_no_e_mail() -> None:
    uid = uuid.uuid4()
    claims = jwt.decode(
        make_token(
            uid,
            email="noa@example.com",
            phone="+972501234567",
            user_metadata={"name": "Noa"},
            app_metadata={"provider": "email"},
        ),
        JWT_SECRET,
        algorithms=["HS256"],
        audience="authenticated",
    )
    sent = rls_claims(User(id=uid, claims=claims))
    assert "noa@example.com" not in sent and "972501234567" not in sent and "Noa" not in sent
    assert '"sub"' in sent and '"role"' in sent and str(uid) in sent


def test_requests_leave_no_token_email_or_location_in_the_logs(
    client, world, user, caplog, capsys
) -> None:
    caplog.set_level(logging.DEBUG)
    email = "noa.private@example.com"
    token = make_token(user, email=email)
    headers = {"Authorization": f"Bearer {token}"}
    lat, lon = 32.0712345, 34.7812345
    client.put(
        "/me/profile",
        json={"neighborhood_lat": lat, "neighborhood_lon": lon, "consent_location": True},
        headers=headers,
    )
    loc = {"lon": lon, "lat": lat, "radius_m": 5000}
    item = {"canonical_id": world.canon["milk3"], "quantity": 1}
    client.post("/compare", json={"items": [item], "location": loc}, headers=headers)
    client.post(
        "/optimize", json={"items": [item], "location": loc, "solver": "milp"}, headers=headers
    )
    client.get("/stores/nearest", params={"chain_id": "t-c1", "lat": lat, "lon": lon})
    client.get("/items/barcode/7290000000000", params={"lat": lat, "lon": lon})
    client.post(
        "/me/alerts",
        json={"canonical_id": world.canon["milk3"], "threshold_unit_price": "5"},
        headers=headers,
    )
    client.get("/me/profile", headers={"Authorization": "Bearer garbage"})
    out = capsys.readouterr()
    # the test client's own httpx logger prints the URLs it requests; that is the test, not the app
    app_records = [
        r.getMessage() for r in caplog.records if not r.name.startswith(("httpx", "asyncio"))
    ]
    logged = "\n".join(app_records) + out.out + out.err
    for needle in (
        token,
        token.split(".")[1],
        email,
        "32.0712345",
        "34.7812345",
        "32.071",
        "34.781",
    ):
        assert needle not in logged, f"{needle!r} was logged"
    assert not re.search(r"Bearer\s+\S{20,}", logged)


# --- headers ---------------------------------------------------------------------------------------


def test_every_response_has_the_hardening_headers(client, user) -> None:
    for r in (
        client.get("/health"),
        client.get("/me/profile", headers=h(user)),
        client.get("/me/profile"),  # a 401
        client.post("/parse-list", json={}),  # a 422
        client.get("/nope"),  # a 404
    ):
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert r.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_per_user_responses_are_not_cacheable(client, user) -> None:
    assert client.get("/me/profile", headers=h(user)).headers["cache-control"] == "no-store"
    assert (
        client.get("/me/lists", headers={}).headers["cache-control"] == "no-store"
    )  # also the 401
    assert (
        client.post("/beta/join", json={"code": "ABCDEF"}, headers=h(user)).headers["cache-control"]
        == "no-store"
    )
    assert "no-store" not in client.get("/health").headers.get("cache-control", "")


def test_the_docs_keep_working_without_the_api_csp(client) -> None:
    r = client.get("/docs")
    assert r.status_code == 200 and "content-security-policy" not in r.headers
    assert client.get("/openapi.json").status_code == 200


def test_hsts_only_over_https(client) -> None:
    assert "strict-transport-security" not in client.get("/health").headers
    r = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert r.headers["strict-transport-security"].startswith("max-age=31536000")


# --- CORS ------------------------------------------------------------------------------------------


def preflight(
    client, origin: str, method: str = "POST", headers: str = "authorization,content-type"
):
    return client.options(
        "/me/lists",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        },
    )


def test_cors_allows_only_the_configured_origins(client) -> None:
    allowed = get_settings().cors_origins
    assert "*" not in allowed, "a wildcard origin would let any site call the API from a browser"
    ok = preflight(client, allowed[0])
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == allowed[0]
    for evil in (
        "https://evil.example",
        "http://localhost:3001",
        allowed[0] + ".evil.example",
        "null",
    ):
        r = preflight(client, evil)
        assert "access-control-allow-origin" not in r.headers, evil
        simple = client.get("/health", headers={"Origin": evil})
        assert "access-control-allow-origin" not in simple.headers, evil


def test_cors_never_allows_credentials_and_limits_headers_and_methods(client) -> None:
    origin = get_settings().cors_origins[0]
    r = preflight(client, origin)
    assert "access-control-allow-credentials" not in r.headers
    allowed_headers = {
        x.strip().lower() for x in r.headers["access-control-allow-headers"].split(",")
    }
    ours = {"authorization", "content-type", "x-image-consent"}
    safelisted = {"accept", "accept-language", "content-language"}  # Starlette adds these itself
    assert ours <= allowed_headers <= ours | safelisted
    assert "*" not in r.headers["access-control-allow-headers"]
    methods = {x.strip() for x in r.headers["access-control-allow-methods"].split(",")}
    assert methods == {"GET", "POST", "PUT", "DELETE", "OPTIONS"}
    assert preflight(client, origin, headers="x-evil").status_code == 400
    assert preflight(client, origin, method="PATCH").status_code == 400
    assert preflight(client, origin, method="TRACE").status_code == 400
    # the actual response of an allowed origin carries no credentials flag either
    assert (
        "access-control-allow-credentials"
        not in client.get("/health", headers={"Origin": origin}).headers
    )


def test_the_default_origin_is_the_local_dev_server_only(monkeypatch) -> None:
    monkeypatch.delenv("API_CORS_ORIGINS", raising=False)
    get_settings.cache_clear()
    assert get_settings().cors_origins == ["http://localhost:3000"]
    monkeypatch.setenv(
        "API_CORS_ORIGINS", " https://smartcart.example , ,https://www.smartcart.example"
    )
    get_settings.cache_clear()
    assert get_settings().cors_origins == [
        "https://smartcart.example",
        "https://www.smartcart.example",
    ]


# --- where a location can end up ---------------------------------------------------------------------


def test_coordinates_are_stored_only_rounded_and_only_in_two_user_tables(db) -> None:
    rows = db.execute(
        "SELECT table_name, column_name, numeric_scale FROM information_schema.columns"
        " WHERE table_schema = 'public' AND column_name ~* '(^|_)(lat|lon|lng|latitude|longitude)$'"
        " ORDER BY 1, 2"
    ).fetchall()
    assert {(t, c) for t, c, _ in rows} == {
        ("price_alerts", "neighborhood_lat"),
        ("price_alerts", "neighborhood_lon"),
        ("profiles", "neighborhood_lat"),
        ("profiles", "neighborhood_lon"),
    }
    assert all(scale == 3 for _, _, scale in rows), "about 100 m"


def test_an_alert_stores_the_rounded_point_of_a_consenting_user(client, world, user, db) -> None:
    client.put(
        "/me/profile",
        json={
            "neighborhood_lat": 32.0712345,
            "neighborhood_lon": 34.7812345,
            "consent_location": True,
        },
        headers=h(user),
    )
    r = client.post(
        "/me/alerts",
        json={"canonical_id": world.canon["milk3"], "threshold_unit_price": "5"},
        headers=h(user),
    )
    assert r.status_code == 201
    row = db.execute(
        "SELECT neighborhood_lat::text, neighborhood_lon::text FROM price_alerts"
    ).fetchone()
    assert row == ("32.071", "34.781")


def test_a_request_location_is_never_stored(client, world, user, db) -> None:
    """compare / optimize / barcode / nearest take a point per request and keep none of it."""
    before = db.execute("SELECT count(*) FROM events").fetchone()[0]
    loc = {"lon": 34.7812345, "lat": 32.0712345, "radius_m": 5000}
    item = {"canonical_id": world.canon["milk3"], "quantity": 1}
    client.post("/compare", json={"items": [item], "location": loc}, headers=h(user))
    client.post("/optimize", json={"items": [item], "location": loc}, headers=h(user))
    client.get("/stores/nearest", params={"chain_id": "t-c1", "lat": 32.0712345, "lon": 34.7812345})
    assert db.execute("SELECT count(*) FROM events").fetchone()[0] == before
    assert db.execute("SELECT count(*) FROM profiles").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM search_misses").fetchone()[0] == 0
