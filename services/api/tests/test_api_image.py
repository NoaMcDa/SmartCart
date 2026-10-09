"""POST /parse-image (issues #61, #68): consent, limits, the monthly cap and the fake-provider round
trips for a receipt and a handwritten list, against the seeded MVP catalog. No network, no OCR
binary: the provider is the FakeProvider, which reads text embedded in the test PNG."""

from __future__ import annotations

import io
from decimal import Decimal

import pytest
from PIL import Image

from smartcart_api.embedding import query_embedder, to_pgvector
from smartcart_api.main import app
from smartcart_api.ocr.providers import FakeProvider, OcrError, OcrResult, png_with_text
from smartcart_api.routes.image import get_provider
from smartcart_catalog.seed import load_catalog, seed_all

pytestmark = pytest.mark.db

CONSENT = {"X-Image-Consent": "1"}


@pytest.fixture
def mvp_catalog(db) -> None:
    seed_all(db, load_catalog())
    emb = query_embedder()
    rows = db.execute("SELECT id, display_name_he FROM canonical_products").fetchall()
    with db.cursor() as cur:
        cur.executemany(
            "UPDATE canonical_products SET embedding = %s::vector, embedding_model = %s WHERE id = %s",
            [(to_pgvector(emb.embed_one(name)), emb.model_name, cid) for cid, name in rows],
        )


@pytest.fixture
def fake():
    provider = FakeProvider()
    app.dependency_overrides[get_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_provider, None)


def post(
    client,
    lines: list[str],
    kind: str = "list",
    headers: dict | None = CONSENT,
    data: bytes | None = None,
):
    payload = data if data is not None else png_with_text(lines)
    return client.post(
        "/parse-image",
        data={"kind": kind},
        files={"image": ("photo.png", payload, "image/png")},
        headers=headers or {},
    )


def names(body: dict) -> list[str]:
    return [i["canonical"]["display_name_he"] for i in body["items"]]


# --- consent ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [None, {"X-Image-Consent": "0"}, {"X-Image-Consent": "true"}, {"X-Image-Consent": ""}],
)
def test_no_consent_is_403_and_nothing_is_read(client, fake, headers) -> None:
    r = post(client, ["חלב"], headers=headers)
    assert r.status_code == 403
    assert "X-Image-Consent" in r.json()["detail"]
    assert fake.calls == 0


def test_consent_is_checked_before_the_body_is_parsed(client, fake) -> None:
    r = client.post(
        "/parse-image", content=b"not even multipart", headers={"Content-Type": "text/plain"}
    )
    assert r.status_code == 403


# --- list photo -------------------------------------------------------------------------------


def test_list_photo_round_trip(client, db, mvp_catalog, fake) -> None:
    r = post(client, ["עגבניות", "2 בננות", "תפוחי אדמה", "קולה"], kind="list")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "list" and body["provider"] == "fake" and body["deleted"] is True
    assert body["receipt"] is None
    assert names(body) == ["עגבניות", "בננות", "תפוחי אדמה", "קולה"]
    assert Decimal(body["items"][1]["quantity"]) == 2
    assert body["unresolved"] == []
    assert all(not i["needs_confirmation"] for i in body["items"])


def test_list_distractors_go_to_unresolved_never_to_a_wrong_product(
    client, mvp_catalog, fake
) -> None:
    lines = ["עגבניות", "דגל ישראל", "יין לבן", "xyzzy", "קקק", "בננות", "אקס"]
    body = post(client, lines).json()
    assert names(body) == ["עגבניות", "בננות"]
    assert body["unresolved"] == ["דגל ישראל", "יין לבן", "xyzzy", "קקק", "אקס"]
    # "יין לבן" shares a word with "קמח לבן" and "אקס" looks like "אקונומיקה": both are left to the user
    assert not any(i["not_found"] for i in body["items"])
    assert all(i["confidence"] >= 0.70 for i in body["items"])


def test_ambiguous_line_stays_but_must_be_confirmed(client, mvp_catalog, fake) -> None:
    body = post(client, ["חלב"]).json()
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert row["needs_confirmation"] and row["candidates"]


def test_list_photo_with_no_text_returns_empty(client, mvp_catalog, fake) -> None:
    body = post(client, []).json()
    assert body["items"] == [] and body["unresolved"] == [] and body["deleted"] is True


def test_tesseract_list_rows_are_all_flagged(client, mvp_catalog) -> None:
    class Tess(FakeProvider):
        name = "tesseract"

        def read(self, image, kind):
            r = super().read(image, kind)
            return OcrResult(r.lines, "tesseract", 0.0)

    app.dependency_overrides[get_provider] = lambda: Tess()
    try:
        body = post(client, ["עגבניות", "בננות"]).json()
    finally:
        app.dependency_overrides.pop(get_provider, None)
    assert body["provider"] == "tesseract"
    assert [i["needs_confirmation"] for i in body["items"]] == [True, True]


# --- receipt ----------------------------------------------------------------------------------

RECEIPT = [
    'שופרסל דיל בע"מ',
    "סניף: רמת אביב",
    "ח.פ 520022732",
    "תאריך 08/10/2026 שעה 18:32",
    "עגבניות",
    '0.532 ק"ג X 9.90 5.27',
    'בננות 1.120 ק"ג 11.20',
    "תפוחי אדמה 6.90",
    "ביצים L 12 יח' 14.90",
    "חלב תנובה 3% 1 ל' 8.90",
    "סליל מכנסיים צבעוני 4.00",
    "הנחת מועדון -2.00",
    "פיקדון 0.30",
    'סה"כ פריטים 6',
    "לתשלום 42.27",
    'מע"מ 18% 6.45',
    "אשראי ויזה ****1234",
]


def test_receipt_round_trip(client, mvp_catalog, fake) -> None:
    r = post(client, RECEIPT, kind="receipt")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "receipt" and body["deleted"] is True
    receipt = body["receipt"]
    assert receipt["chain_hint"] == "7290027600007"
    assert receipt["store_hint"] == "רמת אביב"
    assert Decimal(receipt["total"]) == Decimal("42.27")
    assert [ln["text"] for ln in receipt["lines"]] == [
        "עגבניות",
        "בננות",
        "תפוחי אדמה",
        "ביצים L 12 יחידות",
        "חלב תנובה 3% 1 ליטר",
        "סליל מכנסיים צבעוני",
    ]
    by_name = {i["canonical"]["display_name_he"]: i for i in body["items"]}
    tomatoes = by_name["עגבניות"]
    assert (Decimal(tomatoes["quantity"]), tomatoes["unit"], tomatoes["is_weighed"]) == (
        Decimal("0.532"),
        "kg",
        True,
    )
    bananas = by_name["בננות"]
    assert (Decimal(bananas["quantity"]), bananas["unit"]) == (Decimal("1.120"), "kg")
    assert "תפוחי אדמה" in by_name
    # the receipt's own price per line is reported
    prices = {ln["text"]: ln["price"] for ln in receipt["lines"]}
    assert Decimal(prices["עגבניות"]) == Decimal("5.27")
    # the milk line prints a brand and a size; it still resolves (brand and size are not part of
    # the "any brand" catalog), and as an ambiguity (3 % milk exists in two shelf-life variants)
    # the user is asked
    milk = [i for i in body["items"] if i["canonical"]["display_name_he"].startswith("חלב")]
    assert len(milk) == 1 and milk[0]["confidence"] >= 0.70 and milk[0]["needs_confirmation"]
    eggs = by_name["ביצים L"]  # the 12 in "12 יח'" is the pack, not a purchased quantity
    assert Decimal(eggs["quantity"]) == 1
    # a line the catalog does not carry is listed as read, not matched to something else
    assert any("סליל" in u for u in body["unresolved"])
    assert not any("סליל" in i["input_text"] for i in body["items"])


def test_receipt_repeated_products_are_merged_with_summed_quantity(
    client, mvp_catalog, fake
) -> None:
    body = post(client, ["תפוחי אדמה 6.90", "תפוחי אדמה 6.90", "בננות 5.00"], kind="receipt").json()
    potatoes = [i for i in body["items"] if i["canonical"]["display_name_he"] == "תפוחי אדמה"]
    assert len(potatoes) == 1 and Decimal(potatoes[0]["quantity"]) == 2
    assert len(body["receipt"]["lines"]) == 3  # what was read is shown as read


def test_receipt_with_unknown_chain_has_no_hint(client, mvp_catalog, fake) -> None:
    body = post(client, ["סופר השכונה", "תפוחי אדמה 6.90"], kind="receipt").json()
    assert body["receipt"]["chain_hint"] is None


# --- cap --------------------------------------------------------------------------------------


def test_image_cap_returns_429_and_counts_only_successful_reads(
    client, db, mvp_catalog, fake, monkeypatch
) -> None:
    monkeypatch.setenv("OCR_MONTHLY_IMAGE_CAP", "2")
    assert post(client, ["בננות"]).status_code == 200
    assert post(client, ["בננות"]).status_code == 200
    r = post(client, ["בננות"])
    assert r.status_code == 429
    images, usd = db.execute("SELECT sum(images), sum(est_cost_usd) FROM ocr_usage").fetchone()
    assert (images, usd) == (2, 0)


def test_a_failed_read_is_not_counted(client, db, mvp_catalog, monkeypatch) -> None:
    class Broken(FakeProvider):
        def read(self, image, kind):
            raise OcrError("boom")

    app.dependency_overrides[get_provider] = lambda: Broken()
    try:
        r = post(client, ["בננות"])
    finally:
        app.dependency_overrides.pop(get_provider, None)
    assert r.status_code == 502
    assert db.execute("SELECT count(*) FROM ocr_usage").fetchone()[0] == 0


class PricedProvider(FakeProvider):
    """Named like the paid provider, so the cap expects 0.01 USD for the next image."""

    def __init__(self, cost: float) -> None:
        super().__init__(name="claude")
        self.cost = cost

    def read(self, image, kind):
        r = super().read(image, kind)
        return OcrResult(r.lines, "claude", self.cost)


def test_dollar_cap_uses_the_measured_cost_and_the_expected_next_one(
    client, db, mvp_catalog, monkeypatch
) -> None:
    monkeypatch.setenv("OCR_MONTHLY_USD_CAP", "0.012")
    provider = PricedProvider(0.004)
    app.dependency_overrides[get_provider] = lambda: provider
    try:
        assert post(client, ["בננות"]).status_code == 200  # 0 + 0.01 expected <= 0.012
        usd = db.execute("SELECT est_cost_usd FROM ocr_usage WHERE provider = 'claude'").fetchone()[
            0
        ]
        assert usd == Decimal("0.0040")
        assert post(client, ["בננות"]).status_code == 429  # 0.004 + 0.01 > 0.012
    finally:
        app.dependency_overrides.pop(get_provider, None)
    assert provider.cost == 0.004


def test_cap_defaults_are_2000_images_and_20_dollars(monkeypatch) -> None:
    from smartcart_api.ocr import config

    monkeypatch.delenv("OCR_MONTHLY_IMAGE_CAP", raising=False)
    monkeypatch.delenv("OCR_MONTHLY_USD_CAP", raising=False)
    assert config.image_cap() == 2000 and config.usd_cap() == Decimal(20)


def test_usage_rows_carry_no_user_or_image_reference(db) -> None:
    cols = {
        r[0]
        for r in db.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'ocr_usage'"
        ).fetchall()
    }
    assert cols == {"month", "provider", "images", "est_cost_usd", "updated_at"}


# --- providers --------------------------------------------------------------------------------


def test_no_provider_configured_is_503(client, monkeypatch) -> None:
    from smartcart_api.ocr import providers

    monkeypatch.setenv("OCR_PROVIDER", "auto")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(providers, "tesseract_available", lambda: False)
    r = post(client, ["חלב"])
    assert r.status_code == 503
    assert "no OCR provider configured" in r.json()["detail"]


def test_provider_env_selects_the_fake_provider(client, mvp_catalog, monkeypatch) -> None:
    monkeypatch.setenv("OCR_PROVIDER", "fake")
    r = post(client, ["בננות"])
    assert r.status_code == 200 and r.json()["provider"] == "fake"


def test_jpeg_without_embedded_text_reads_nothing_with_the_fake(client, mvp_catalog, fake) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), "white").save(buf, "JPEG")
    body = post(client, [], data=buf.getvalue()).json()
    assert body["items"] == []


def test_invalid_kind_is_422(client, fake) -> None:
    r = client.post(
        "/parse-image",
        data={"kind": "recipe"},
        files={"image": ("a.png", png_with_text(["x"]), "image/png")},
        headers=CONSENT,
    )
    assert r.status_code == 422


def test_missing_image_is_422(client, fake) -> None:
    assert client.post("/parse-image", data={"kind": "list"}, headers=CONSENT).status_code == 422
