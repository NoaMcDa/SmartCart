"""``POST /parse-image``: a receipt or a handwritten list photo to list rows (issues #61, #68).

multipart/form-data: ``kind`` ("receipt" | "list") and ``image`` (JPEG, PNG or WebP by magic
bytes, at most 8 MB, at most 25 megapixels).

Order of checks, cheapest first:

1. ``X-Image-Consent: 1`` or 403, before the body is read (the user agreed to photo processing).
2. A body over 8 MB + the multipart envelope is cut off with 413 while it streams in.
3. 503 when no OCR provider is configured (``OCR_PROVIDER``), 429 when the monthly cap of images
   or estimated dollars would be passed (``OCR_MONTHLY_IMAGE_CAP``, ``OCR_MONTHLY_USD_CAP``).
4. 415 for a format that is not JPEG/PNG/WebP, 413 over 8 MB or 25 MP, 422 when undecodable.
5. The photo is rotated by EXIF, downscaled to 2400 px and read by the provider.
6. A list photo: lines -> ``/parse-list`` matcher. A receipt: rule-based structuring
   (``smartcart_catalog.receipt``) -> the same matcher with the printed quantity. A best hit under
   0.70 goes to ``unresolved`` with the line as read, never a guess (D5).

Deletion guarantee (D11): the bytes, the decoded image and the raw OCR text live in this
function's locals. They are not written to disk (no temp file: the multipart parser is told to
keep the upload in memory, Pillow decodes from ``BytesIO``, Tesseract reads stdin), not logged,
not stored, and the references are dropped before the response. ``deleted`` is always true.
Only a count and the estimated cost go to ``ocr_usage``, with no user id.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Annotated, Any, Literal

import psycopg
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.routing import APIRoute
from starlette.formparsers import MultiPartParser

from smartcart_api import schemas
from smartcart_api.db import get_conn
from smartcart_api.ocr import usage
from smartcart_api.ocr.image import MAX_BYTES, ImageError, prepare
from smartcart_api.ocr.providers import (
    NoProvider,
    OcrError,
    Provider,
    expected_cost,
    select_provider,
)
from smartcart_api.ocr.rows import rows_from_list_lines, rows_from_receipt
from smartcart_catalog.receipt import parse_receipt

log = logging.getLogger("smartcart.ocr")

CONSENT_HEADER = "x-image-consent"
MAX_BODY = MAX_BYTES + 64 * 1024  # the photo plus the multipart envelope

# Starlette spools an upload to a temp file once it passes 1 MB. A photo is up to 8 MB and must
# never reach the disk, so this route's uploads stay in memory (the body is capped at MAX_BODY by
# the route class below, so memory is bounded).
MultiPartParser.spool_max_size = MAX_BODY + 1


class _ImageRoute(APIRoute):
    """Refuse before reading the body: no consent (403), or a body that is too large (413)."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        inner = super().get_route_handler()

        async def handler(request: Request) -> Response:
            if request.headers.get(CONSENT_HEADER) != "1":
                raise HTTPException(
                    status_code=403, detail="photo processing needs consent (X-Image-Consent: 1)"
                )
            declared = request.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > MAX_BODY:
                raise HTTPException(status_code=413, detail="the image is larger than 8 MB")
            received = 0
            original = request.receive

            async def limited() -> Any:
                nonlocal received
                message = await original()
                if message["type"] == "http.request":
                    received += len(message.get("body", b""))
                    if received > MAX_BODY:
                        raise HTTPException(status_code=413, detail="the image is larger than 8 MB")
                return message

            return await inner(Request(request.scope, limited, request._send))

        return handler


router = APIRouter(tags=["list"], route_class=_ImageRoute)


def get_provider() -> Provider:
    try:
        return select_provider()
    except NoProvider as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.post("/parse-image", response_model=schemas.ParseImageResponse)
def parse_image(
    kind: Annotated[Literal["receipt", "list"], Form()],
    image: Annotated[UploadFile, File(description="JPEG, PNG or WebP, at most 8 MB")],
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
    provider: Annotated[Provider, Depends(get_provider)],
) -> schemas.ParseImageResponse:
    usage.check_cap(conn, expected_cost(provider))
    data: bytes | None = image.file.read(MAX_BYTES + 1)
    pil = None
    lines: list[str] = []
    try:
        pil = prepare(data)
        data = None
        result = provider.read(pil, kind)
        lines = list(result.lines)
        provider_name, cost = result.provider, result.est_cost_usd
    except ImageError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from None
    except OcrError:
        raise HTTPException(
            status_code=502, detail="the image could not be read, try again"
        ) from None
    finally:
        data = pil = None
        image.file.close()
    usage.record(conn, provider_name, cost)

    try:
        if kind == "list":
            rows, unresolved = rows_from_list_lines(
                conn, lines, confirm_all=provider_name == "tesseract"
            )
            summary = None
        else:
            receipt = parse_receipt(lines)
            rows, unresolved = rows_from_receipt(conn, receipt)
            summary = schemas.ReceiptSummary(
                chain_hint=receipt.chain_id,
                store_hint=receipt.store_hint,
                total=receipt.total,
                lines=[
                    schemas.ReceiptLine(text=i.text, quantity=i.quantity, price=i.price)
                    for i in receipt.items
                ],
            )
    finally:
        n_lines = len(lines)
        lines = []  # drop the raw OCR text
    log.info(
        "parse-image kind=%s provider=%s lines=%d items=%d unresolved=%d usd=%.4f",
        kind,
        provider_name,
        n_lines,
        len(rows),
        len(unresolved),
        cost,
    )
    return schemas.ParseImageResponse(
        kind=kind,
        provider=provider_name,
        items=rows,
        unresolved=unresolved,
        receipt=summary,
        deleted=True,
    )
