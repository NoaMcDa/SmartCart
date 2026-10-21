"""Server-side requests to addresses a user typed: the recipe page fetch (``POST /parse-recipe``) and
the web push endpoint (``POST /me/push-subscriptions``, delivered by ``alerts-run``).

No test here touches the network: the resolver is injected and the transport is a mock.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from api_world import make_token

from smartcart_api import recipe_fetch
from smartcart_api.push import PushTarget, WebPushSender, deliverable, validate_endpoint
from smartcart_api.recipe_fetch import (
    FetchError,
    check_url,
    http_fetch,
    public_address,
)

PUBLIC_IP = "93.184.216.34"


# --- which addresses count as public ------------------------------------------------------------


@pytest.mark.parametrize(
    "addr",
    [
        "127.0.0.1",
        "127.255.255.254",
        "10.0.0.1",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.1.1",
        "169.254.169.254",  # cloud metadata
        "100.64.0.1",  # carrier-grade NAT
        "100.127.255.255",
        "0.0.0.0",
        "0.1.2.3",
        "192.0.0.8",
        "192.0.2.1",  # documentation
        "198.18.0.1",  # benchmarking
        "198.51.100.1",
        "203.0.113.1",
        "224.0.0.1",  # multicast
        "239.255.255.250",
        "240.0.0.1",  # reserved
        "255.255.255.255",
        "::1",
        "::",
        "fe80::1",
        "fe80::1%eth0",
        "fc00::1",
        "fd12:3456::1",
        "ff02::1",
        "::ffff:127.0.0.1",  # IPv4-mapped
        "::ffff:10.0.0.1",
        "::ffff:169.254.169.254",
        "64:ff9b::7f00:1",  # NAT64 of 127.0.0.1
        "64:ff9b::a9fe:a9fe",  # NAT64 of 169.254.169.254
        "2002:7f00:1::1",  # 6to4 of 127.0.0.1
        "2002:a9fe:a9fe::1",
        "2001:db8::1",  # documentation
    ],
)
def test_special_purpose_addresses_are_not_public(addr: str) -> None:
    assert public_address(addr) is False, addr


@pytest.mark.parametrize(
    "addr",
    [PUBLIC_IP, "8.8.8.8", "1.1.1.1", "2606:4700:4700::1111", "::ffff:8.8.8.8", "64:ff9b::808:808"],
)
def test_public_addresses_are_public(addr: str) -> None:
    assert public_address(addr) is True, addr


# --- URLs ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://93.184.216.34/r",
        "gopher://93.184.216.34/_x",
        "javascript:alert(1)",
        "data:text/html,<x>",
        "//93.184.216.34/r",
        "http:/93.184.216.34",
        "http://",
        "http:///r",
        "93.184.216.34/r",
        "http://user@93.184.216.34/r",
        "http://user:pw@93.184.216.34/r",
        "http://93.184.216.34@127.0.0.1/",
        "http://93.184.216.34:22/r",
        "http://93.184.216.34:8080/r",
        "http://93.184.216.34:0/r",
        "http://93.184.216.34:99999/r",
        "https://93.184.216.34:444/r",
    ],
)
def test_url_shapes_that_are_refused_before_resolving(url: str) -> None:
    def no_dns(host: str) -> list[str]:
        raise AssertionError("must be refused without a lookup")

    with pytest.raises(FetchError) as err:
        check_url(url, resolve=no_dns)
    assert err.value.status == 422


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/r",
        "http://LOCALHOST/r",
        "http://localhost./r",
        "http://127.0.0.1/r",
        "http://127.1/r",  # short form
        "http://0x7f.0.0.1/r",  # hex octet
        "http://0177.0.0.1/r",  # octal octet
        "http://2130706433/r",  # whole address as one decimal number
        "http://0x7f000001/r",
        "http://[::1]/r",
        "http://[::ffff:7f00:1]/r",
        "http://[0:0:0:0:0:ffff:7f00:1]/r",
        "http://0.0.0.0/r",
        "http://169.254.169.254/latest/meta-data/",
        "http://[fd00:ec2::254]/latest/meta-data/",
        "http://10.1.2.3/r",
        "http://192.168.0.1/r",
        "http://100.64.0.1/r",
    ],
)
def test_loopback_private_and_obfuscated_hosts_are_refused_with_the_real_resolver(url: str) -> None:
    with pytest.raises(FetchError) as err:
        check_url(url)  # the system resolver: numeric forms need no network
    assert err.value.status == 422, url


def test_a_name_that_resolves_to_any_private_address_is_refused() -> None:
    for answers in (
        ["127.0.0.1"],
        [PUBLIC_IP, "10.0.0.5"],  # one bad answer among good ones
        ["::1", PUBLIC_IP],
        ["::ffff:192.168.0.1"],
        [],
    ):
        with pytest.raises(FetchError):
            check_url("https://recipes.example/r", resolve=lambda host, a=answers: a)


def test_an_unresolvable_host_is_refused() -> None:
    def broken(host: str) -> list[str]:
        raise OSError("no such host")

    with pytest.raises(FetchError, match="resolved"):
        check_url("https://nope.example/", resolve=broken)


# --- DNS rebinding: one lookup, and the request goes to the address that was checked ---------------


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_the_request_is_pinned_to_the_checked_address_and_keeps_the_name_for_tls() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    lookups: list[str] = []

    def resolve(host: str) -> list[str]:
        lookups.append(host)
        return [PUBLIC_IP]

    http_fetch("https://recipes.example/pasta?x=1", _client(handler), resolve)
    (req,) = seen
    assert req.url.host == PUBLIC_IP and req.url.path == "/pasta" and req.url.query == b"x=1"
    assert req.headers["host"] == "recipes.example"
    assert req.extensions["sni_hostname"] == "recipes.example"  # certificate check on the name
    assert lookups == ["recipes.example"], "exactly one DNS lookup, none at connect time"


def test_a_name_that_changes_its_answer_after_the_check_gets_nothing() -> None:
    """The rebinding attack: first answer public (passes the check), second answer private. There is
    no second lookup, so the request can only go to the first one."""
    answers = iter([[PUBLIC_IP], ["127.0.0.1"], ["127.0.0.1"]])
    hosts_requested: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        hosts_requested.append(req.url.host)
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"ok")

    http_fetch("http://rebind.example/r", _client(handler), lambda host: next(answers))
    assert hosts_requested == [PUBLIC_IP]


def test_port_and_ipv6_pinning() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"ok")

    http_fetch("http://v6.example:80/r", _client(handler), lambda h: ["2606:4700:4700::1111"])
    assert seen[0].url.host == "2606:4700:4700::1111"
    assert seen[0].headers["host"] == "v6.example:80"


def test_a_redirect_to_a_name_that_resolves_privately_is_refused() -> None:
    zone = {"good.example": [PUBLIC_IP], "inside.example": ["10.0.0.7"]}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.headers["host"] == "good.example":
            return httpx.Response(302, headers={"location": "http://inside.example/admin"})
        raise AssertionError("the private host was requested")

    with pytest.raises(FetchError) as err:
        http_fetch("http://good.example/r", _client(handler), lambda h: zone[h])
    assert err.value.status == 422


@pytest.mark.parametrize(
    "location",
    [
        "file:///etc/passwd",
        "ftp://93.184.216.34/x",
        "gopher://93.184.216.34/",
        "http://93.184.216.34:8080/x",
        "http://user:pw@93.184.216.34/",
        "http://[::1]/",
        "//127.0.0.1/x",
        "http://127.1/",
        "http://2130706433/",
    ],
)
def test_redirect_targets_are_checked_like_the_first_url(location: str) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/r":
            return httpx.Response(302, headers={"location": location})
        raise AssertionError("the redirect target was requested")

    with pytest.raises(FetchError) as err:
        http_fetch(f"http://{PUBLIC_IP}/r", _client(handler))
    assert err.value.status == 422


# --- the response -------------------------------------------------------------------------------


def test_a_compressed_response_is_refused_because_it_was_not_asked_for() -> None:
    """A small gzip body can inflate far beyond the cap inside one network chunk."""
    sent: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        sent.append(req)
        return httpx.Response(
            200, headers={"content-type": "text/html", "content-encoding": "gzip"}, content=b"x"
        )

    with pytest.raises(FetchError, match="compressed"):
        http_fetch(f"http://{PUBLIC_IP}/r", _client(handler))
    assert sent[0].headers["accept-encoding"] == "identity"


def test_a_declared_length_over_the_cap_is_refused_without_reading() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "text/html",
                "content-length": str(recipe_fetch.MAX_BYTES + 1),
            },
            content=b"x" * 10,
        )

    with pytest.raises(FetchError, match="larger than 2 MB"):
        http_fetch(f"http://{PUBLIC_IP}/r", _client(handler))


@pytest.mark.parametrize(
    "ctype",
    ["application/json", "application/pdf", "image/png", "application/octet-stream", "text/xml"],
)
def test_only_html_and_plain_text_are_read(ctype: str) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": ctype}, content=b"{}")

    with pytest.raises(FetchError, match="not a web page"):
        http_fetch(f"http://{PUBLIC_IP}/r", _client(handler))


def test_the_time_budget_covers_the_whole_fetch_not_each_hop(monkeypatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(recipe_fetch.time, "monotonic", lambda: now[0])

    def handler(req: httpx.Request) -> httpx.Response:
        now[0] += 3.0  # each hop answers just inside the per-request timeout
        return httpx.Response(302, headers={"location": f"http://{PUBLIC_IP}/again"})

    with pytest.raises(FetchError, match="too long") as err:
        http_fetch(f"http://{PUBLIC_IP}/r", _client(handler))
    assert err.value.status == 502


def test_the_route_maps_a_fetch_refusal_to_its_status(client, monkeypatch) -> None:
    def refuse(url: str) -> str:
        raise FetchError(422, "the host is not a public address")

    from smartcart_api.main import app
    from smartcart_api.recipe_fetch import get_fetcher

    app.dependency_overrides[get_fetcher] = lambda: refuse
    try:
        r = client.post("/parse-recipe", json={"url": "http://127.0.0.1/recipe"})
    finally:
        app.dependency_overrides.pop(get_fetcher, None)
    assert r.status_code == 422 and r.json()["detail"] == "the host is not a public address"


# --- the push endpoint ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/abc",  # not https
        "ftp://push.example.com/x",
        "https://127.0.0.1/x",
        "https://10.0.0.5/x",
        "https://[::1]/x",
        "https://169.254.169.254/latest/meta-data",
        "https://2130706433/x",
        "https://localhost/x",
        "https://localhost./x",
        "https://intranet/x",  # a single label
        "https://db.internal/x",
        "https://printer.local/x",
        "https://push.example.com:8443/x",
        "https://user:pw@push.example.com/x",
        "https:///x",
        "https://",
        "push.example.com/x",
        "",
    ],
)
def test_push_endpoints_that_could_reach_the_inside_are_refused(client, endpoint: str) -> None:
    uid = uuid.uuid4()
    sub = {"endpoint": endpoint, "p256dh": "k", "auth": "a"}
    headers = {"Authorization": f"Bearer {make_token(uid)}"}
    assert client.post("/me/push-subscriptions", json=sub, headers=headers).status_code == 422
    with pytest.raises(ValueError):
        validate_endpoint(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/abc",
        "https://updates.push.services.mozilla.com/wpush/v2/abc",
        "https://wns2-par02p.notify.windows.com/w/?token=abc",
        "https://web.push.apple.com/abc",
    ],
)
def test_real_push_services_are_accepted(endpoint: str) -> None:
    assert validate_endpoint(endpoint) == endpoint


def test_an_operator_can_pin_the_push_services(monkeypatch) -> None:
    monkeypatch.setenv(
        "API_PUSH_ENDPOINT_HOSTS",
        "fcm.googleapis.com, .push.services.mozilla.com,.notify.windows.com",
    )
    for ok in (
        "https://fcm.googleapis.com/fcm/send/a",
        "https://updates.push.services.mozilla.com/wpush/v2/a",
        "https://wns2-par02p.notify.windows.com/w/?token=a",
    ):
        validate_endpoint(ok)
    for bad in (
        "https://evil.example.com/x",
        "https://fcm.googleapis.com.evil.example/x",  # a suffix trick
        "https://notfcm.googleapis.com/x",
        "https://evilpush.services.mozilla.com/x",
    ):
        with pytest.raises(ValueError):
            validate_endpoint(bad)


def test_the_sender_checks_where_the_name_points_now(monkeypatch) -> None:
    import pywebpush

    called: list[object] = []
    monkeypatch.setattr(pywebpush, "webpush", lambda **kw: called.append(kw))
    sender = WebPushSender("priv", "pub", "mailto:x@example.com")
    target = PushTarget(1, "https://push.example.com/a", "p", "a")

    monkeypatch.setattr(recipe_fetch, "_resolve", lambda host: ["10.0.0.9"])
    assert deliverable(target.endpoint) is False
    assert sender(target, {}) == 410, "a subscription that points inside is dropped"

    def down(host: str) -> list[str]:
        raise OSError("temporary failure")

    monkeypatch.setattr(recipe_fetch, "_resolve", down)
    assert deliverable(target.endpoint) is None
    assert sender(target, {}) == 0, "a lookup failure is retried on the next run"
    assert called == [], "nothing was sent in either case"

    monkeypatch.setattr(recipe_fetch, "_resolve", lambda host: [PUBLIC_IP])
    assert deliverable(target.endpoint) is True
