"""Request-level protections that apply to every route (docs/security-review.md).

* ``BodyLimitMiddleware``: a request body over the limit is refused with 413 before a route reads
  it. Uvicorn has no body limit of its own, so without this a 1 GB JSON post to ``/parse-list`` is
  buffered in memory before validation runs. ``/parse-image`` has its own larger limit (the photo
  plus the multipart envelope, enforced again in ``routes/image.py``). A declared
  ``Content-Length`` over the limit is refused at once; a chunked body is counted as it streams.
* ``SecurityHeadersMiddleware``: ``nosniff`` and ``no-referrer`` everywhere, a locked-down CSP on
  the JSON routes (not on ``/docs``, which loads Swagger UI from a CDN), ``Cache-Control: no-store``
  on everything per-user, HSTS when the request came in over https.
* Exception handlers: an unhandled error answers a fixed JSON body (no SQL, no traceback, no
  other user's data; the detail goes to the log), a database that is down or a pool that is
  exhausted answers 503, and a value Postgres refuses (out of range, malformed) answers 422.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import DataError, IntegrityError, InterfaceError, OperationalError
from psycopg.errors import UniqueViolation
from psycopg_pool import PoolTimeout
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = structlog.get_logger("smartcart_api.security")

# Paths with a larger body than the default: path -> bytes. The photo route allows the 8 MB image
# plus the multipart envelope (the same number routes/image.py enforces).
PATH_LIMITS: dict[str, int] = {"/parse-image": 8 * 1024 * 1024 + 64 * 1024}

_PER_USER_PREFIXES = ("/me", "/beta", "/lists/accept")
_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


def _too_large(limit: int) -> HTTPException:
    return HTTPException(status_code=413, detail=f"the request body is larger than {limit} bytes")


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, default_limit: int | None = None) -> None:
        self.app = app
        self.default_limit = default_limit

    def _limit(self, path: str) -> int:
        if path in PATH_LIMITS:
            return PATH_LIMITS[path]
        if self.default_limit is not None:
            return self.default_limit
        from smartcart_api.settings import get_settings

        return get_settings().max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self._limit(scope["path"])
        for name, value in scope["headers"]:
            if name == b"content-length":
                if value.isdigit() and int(value) > limit:
                    response = JSONResponse({"detail": _too_large(limit).detail}, status_code=413)
                    await response(scope, receive, send)
                    return
                break
        received = 0

        async def limited() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _too_large(limit)
            return message

        await self.app(scope, limited, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        headers = dict(scope["headers"])
        https = (
            scope.get("scheme") == "https"
            or headers.get(b"x-forwarded-proto", b"").split(b",")[0].strip() == b"https"
        )

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                out = list(message.get("headers", []))
                present = {k.lower() for k, _ in out}

                def add(name: bytes, value: bytes) -> None:
                    if name not in present:
                        out.append((name, value))

                add(b"x-content-type-options", b"nosniff")
                add(b"referrer-policy", b"no-referrer")
                if not path.startswith(_DOC_PATHS):
                    add(b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")
                if path.startswith(_PER_USER_PREFIXES):
                    add(b"cache-control", b"no-store")
                if https:
                    add(b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                message = {**message, "headers": out}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _printable(value: object) -> object:
    """A string that survives UTF-8 encoding (a client can send a lone surrogate as a key)."""
    return value.encode("utf-8", "replace").decode("utf-8") if isinstance(value, str) else value


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's own 422 body echoes each rejected value (``input``) and the validator's
        # exception (``ctx``). Echoing arbitrary input breaks the response itself (a ``NaN`` token
        # or a lone surrogate cannot be serialized: a 500 for a bad request) and returns whatever
        # was posted, up to the body limit. The location, the rule and the message are enough.
        errors = [
            {
                "type": e.get("type"),
                "loc": [_printable(part) for part in e.get("loc", ())],
                "msg": _printable(e.get("msg")),
            }
            for e in exc.errors()
        ]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.exception_handler(PoolTimeout)
    @app.exception_handler(OperationalError)
    @app.exception_handler(InterfaceError)
    async def database_unavailable(request: Request, exc: Exception) -> JSONResponse:
        log.error("database unavailable", path=request.url.path, error=type(exc).__name__)
        return JSONResponse(
            {"detail": "the service is busy, try again shortly"},
            status_code=503,
            headers={"Retry-After": "5"},
        )

    @app.exception_handler(DataError)
    async def bad_value(request: Request, exc: Exception) -> JSONResponse:
        log.warning(
            "value refused by the database", path=request.url.path, error=type(exc).__name__
        )
        return JSONResponse({"detail": "a value is out of range or malformed"}, status_code=422)

    @app.exception_handler(UniqueViolation)
    async def duplicate(request: Request, exc: Exception) -> JSONResponse:
        log.warning("duplicate refused", path=request.url.path, error=type(exc).__name__)
        return JSONResponse({"detail": "this record already exists"}, status_code=409)

    @app.exception_handler(IntegrityError)
    async def integrity(request: Request, exc: Exception) -> JSONResponse:
        # A foreign key to a row that does not exist, a CHECK, a NOT NULL: the caller sent an id or a
        # value the data does not allow. The constraint's name and the row stay in the log.
        log.warning("constraint refused", path=request.url.path, error=type(exc).__name__)
        return JSONResponse(
            {"detail": "a referenced record does not exist or a value is not allowed"},
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        # No traceback and no message in the body; the server log has the exception (uvicorn
        # prints it when this handler returns).
        log.error("unhandled error", path=request.url.path, error=type(exc).__name__)
        # This response is made outside the middleware above, so it carries its headers itself.
        return JSONResponse(
            {"detail": "internal error"},
            status_code=500,
            headers={
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
            },
        )
