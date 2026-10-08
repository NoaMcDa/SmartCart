"""``POST /parse-image``: a receipt or a handwritten list photo to list rows (issues #61, #68).

Contract only on the base branch; the implementation (OCR providers, receipt structuring, the
monthly cap and the consent check) lands with the photo workstream. The image is processed in
memory and never stored; the raw OCR text is not stored either (D11).
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from smartcart_api import schemas

router = APIRouter(tags=["list"])


@router.post("/parse-image", response_model=schemas.ParseImageResponse)
def parse_image(
    kind: Annotated[Literal["receipt", "list"], Form()],
    image: Annotated[UploadFile, File(description="JPEG, PNG or WebP, at most 8 MB")],
) -> schemas.ParseImageResponse:
    raise HTTPException(status_code=501, detail="not implemented yet")
