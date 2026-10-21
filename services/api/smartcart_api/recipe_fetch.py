"""Fetch one recipe page for ``POST /parse-recipe`` (issue #71).

Rules, because the server fetches a URL a user typed:

* only ``http`` and ``https`` on the default ports, no credentials in the URL;
* the host must resolve to public addresses only: loopback, private, link-local, multicast,
  reserved and unspecified addresses are refused (no requests into the hosting network);
* only the given page: no links are followed, no robots-guarded crawling, at most
  ``MAX_REDIRECTS`` redirects, each checked like the first URL;
* ``TIMEOUT_S`` seconds per request phase and in total, ``MAX_BYTES`` of body, HTML or plain
  text only.

The fetcher is a dependency (``get_fetcher``) so tests replace it and never use the network.
DNS rebinding: the name is resolved once, the answer is checked, and the request is then sent to
that checked address (the URL's host is replaced by the address, ``Host`` keeps the name, and for
https the TLS server name and the certificate check stay on the name through httpx's
``sni_hostname`` extension). A host that changes its DNS answer between the check and the connect
therefore gets nothing: there is no second lookup. Deploy the API with egress limited to the public
internet as a second line anyway.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

import httpx

TIMEOUT_S = 5.0
MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3
USER_AGENT = "SmartCartRecipe/1.0 (+one page per user request)"
_TYPES = ("text/html", "application/xhtml+xml", "text/plain")

Fetcher = Callable[[str], str]


class FetchError(Exception):
    """``status`` is the HTTP status the API answers: 422 for the URL, 502 for the site."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def public_address(addr: str) -> bool:
    ip = ipaddress.ip_address(addr.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address):
        # An IPv4 address wrapped in an IPv6 one (mapped, 6to4, NAT64) is judged as the IPv4 one.
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip.sixtofour is not None:
            ip = ip.sixtofour
        elif ip in _NAT64:
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    # is_global is false for private, loopback, link-local, carrier-grade NAT (100.64/10),
    # benchmarking, documentation and the other special-purpose ranges.
    return ip.is_global and not (ip.is_multicast or ip.is_unspecified)


_public = public_address


def check_url(url: str, resolve: Callable[[str], list[str]] | None = None) -> list[str]:
    """The addresses of ``url``'s host; raises ``FetchError(422)`` unless ``url`` is an http(s)
    URL of a public host."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError(422, "url must be an http or https link")
    if parts.username or parts.password:
        raise FetchError(422, "url may not carry credentials")
    try:
        port = parts.port
    except ValueError as exc:
        raise FetchError(422, "invalid port") from exc
    if port not in (None, 80, 443):
        raise FetchError(422, "only the default ports are fetched")
    resolve = resolve or _resolve
    try:
        addrs = resolve(parts.hostname)
    except OSError as exc:
        raise FetchError(422, "the host could not be resolved") from exc
    if not addrs or not all(_public(a) for a in addrs):
        raise FetchError(422, "the host is not a public address")
    return addrs


def _pinned(url: str, addrs: list[str]) -> tuple[str, dict[str, str], dict[str, str]]:
    """``url`` aimed at the checked address: (url to request, extra headers, extensions).

    An IP-literal host needs nothing. For a name, the connection goes to ``addrs[0]`` (the whole
    answer set was checked), ``Host`` carries the name, and the TLS handshake still uses the name
    for SNI and for the certificate check."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return url, {}, {}
    addr = addrs[0].split("%", 1)[0]
    literal = f"[{addr}]" if ":" in addr else addr
    netloc = literal if parts.port is None else f"{literal}:{parts.port}"
    host_header = host if parts.port is None else f"{host}:{parts.port}"
    return (
        parts._replace(netloc=netloc).geturl(),
        {"Host": host_header},
        {"sni_hostname": host} if parts.scheme == "https" else {},
    )


def _resolve(host: str) -> list[str]:
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        pass
    return sorted({info[4][0] for info in socket.getaddrinfo(host, None)})


def http_fetch(
    url: str,
    client: httpx.Client | None = None,
    resolve: Callable[[str], list[str]] | None = None,
) -> str:
    """The page at ``url`` as text, under the rules above."""
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_S, follow_redirects=False)
    deadline = time.monotonic() + TIMEOUT_S
    try:
        for _ in range(MAX_REDIRECTS + 1):
            if time.monotonic() > deadline:  # the budget is for the whole fetch, redirects included
                raise FetchError(502, "the recipe page took too long")
            addrs = check_url(url, resolve)
            target, extra, extensions = _pinned(url, addrs)
            try:
                with client.stream(
                    "GET",
                    target,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "text/html, text/plain",
                        # A compressed body is decoded in one piece per network chunk: a small
                        # download can inflate far past the cap before it is counted.
                        "Accept-Encoding": "identity",
                        **extra,
                    },
                    extensions=extensions,
                ) as r:
                    if r.is_redirect and "location" in r.headers:
                        url = urljoin(url, r.headers["location"])
                        continue
                    if r.status_code != 200:
                        raise FetchError(502, f"the recipe page answered {r.status_code}")
                    ctype = r.headers.get("content-type", "text/html").split(";")[0].strip().lower()
                    if ctype not in _TYPES:
                        raise FetchError(422, f"not a web page ({ctype})")
                    if r.headers.get("content-encoding", "identity").strip().lower() not in (
                        "",
                        "identity",
                    ):
                        raise FetchError(
                            422, "the page is compressed although it was not asked to be"
                        )
                    declared = r.headers.get("content-length", "")
                    if declared.isdigit() and int(declared) > MAX_BYTES:
                        raise FetchError(422, "the page is larger than 2 MB")
                    body = bytearray()
                    for chunk in r.iter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            raise FetchError(422, "the page is larger than 2 MB")
                        if time.monotonic() > deadline:
                            raise FetchError(502, "the recipe page took too long")
                    return body.decode(r.encoding or "utf-8", errors="replace")
            except httpx.TimeoutException as exc:
                raise FetchError(502, "the recipe page took too long") from exc
            except httpx.HTTPError as exc:
                raise FetchError(502, "could not fetch the recipe page") from exc
        raise FetchError(502, "too many redirects")
    finally:
        if own:
            client.close()


def get_fetcher() -> Fetcher:
    """FastAPI dependency; tests override it with a fake."""
    return http_fetch
