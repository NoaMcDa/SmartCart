"""Cost estimate for one vision request (synchronous, not batch).

The catalog's ``extract/claude.py`` keeps the *batch* table (50 % discount). Reading a photo is an
interactive request, so it bills at the list price. These are estimates of the bill, not the bill:
check the console. USD per million tokens (input, output); Sonnet 5.5 list price is 2 / 10.
"""

from __future__ import annotations

from decimal import Decimal

SYNC_PRICES_PER_MTOK: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet-5-5": (Decimal("2.00"), Decimal("10.00")),
}

# What a photo is expected to cost before it is read, used by the monthly USD cap to refuse early.
# Estimate: about 1.6k image tokens (the API downscales to ~1568 px) + 300 prompt tokens in, a few
# hundred out. The figure measured from the usage tokens replaces it in ocr_usage after each image.
EXPECTED_USD_PER_IMAGE: dict[str, Decimal] = {
    "claude": Decimal("0.0100"),
    "tesseract": Decimal(0),
    "fake": Decimal(0),
}


def estimate_sync_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
    """Estimated USD for one request, or None for a model without a price entry."""
    prices = SYNC_PRICES_PER_MTOK.get(model)
    if prices is None:
        return None
    p_in, p_out = prices
    usd = (Decimal(input_tokens) * p_in + Decimal(output_tokens) * p_out) / Decimal(1_000_000)
    return usd.quantize(Decimal("0.0001"))
