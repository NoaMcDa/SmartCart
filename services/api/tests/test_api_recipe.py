"""POST /parse-recipe (issue #71): ten Hebrew recipes against the seeded MVP catalog, the URL
path through a fake fetcher, and the fetch rules (no network in any test)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from smartcart_api.embedding import query_embedder, to_pgvector
from smartcart_api.main import app
from smartcart_api.recipe_fetch import MAX_BYTES, FetchError, check_url, get_fetcher, http_fetch
from smartcart_catalog.seed import load_catalog, seed_all

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "recipes.json").read_text(encoding="utf-8"))
RECIPES = FIXTURE["recipes"]


@pytest.fixture
def mvp_catalog(db) -> None:
    """The real seed files (data/*.yaml) with hash embeddings, as the demo stack has them."""
    seed_all(db, load_catalog())
    emb = query_embedder()
    rows = db.execute("SELECT id, display_name_he FROM canonical_products").fetchall()
    with db.cursor() as cur:
        cur.executemany(
            "UPDATE canonical_products SET embedding = %s::vector, embedding_model = %s WHERE id = %s",
            [(to_pgvector(emb.embed_one(name)), emb.model_name, cid) for cid, name in rows],
        )


@pytest.fixture
def pages():
    """A fake fetcher serving the fixture pages; any other URL fails the test."""
    served: dict[str, str] = {r["request"]["url"]: r["request"]["html"] for r in RECIPES if "url" in r["request"]}
    asked: list[str] = []

    def fake(url: str) -> str:
        asked.append(url)
        if url not in served:
            raise FetchError(502, "could not fetch the recipe page")
        return served[url]

    app.dependency_overrides[get_fetcher] = lambda: fake
    yield asked
    app.dependency_overrides.pop(get_fetcher, None)


def _post(client, request: dict):
    body = {k: v for k, v in request.items() if k != "html"}
    return client.post("/parse-recipe", json=body)


@pytest.mark.db
@pytest.mark.parametrize("case", RECIPES, ids=[r["name"] for r in RECIPES])
def test_recipes_become_basket_rows(client, mvp_catalog, pages, case) -> None:
    r = _post(client, case["request"])
    assert r.status_code == 200, r.text
    got, want = r.json(), case["expect"]
    assert got["title"] == want["title"]
    assert got["servings"] == want["servings"]
    rows = [
        (row["canonical"]["display_name_he"], Decimal(row["quantity"]), row["unit"], row["needs_confirmation"])
        for row in got["items"]
    ]
    expected = [(n, Decimal(q), u, c) for n, q, u, c in want["items"]]
    assert len(rows) == len(expected), rows
    for (name, qty, unit, confirm), (w_name, w_qty, w_unit, w_confirm) in zip(rows, expected, strict=True):
        if w_name.startswith("*"):  # ambiguous: any canonical of that kind, the user picks
            assert name.startswith(w_name[1:]), (name, w_name)
        else:
            assert name == w_name, rows
        assert (qty, unit, confirm) == (w_qty, w_unit, w_confirm), (name, rows)
    assert got["unresolved"] == want["unresolved"]
    for row in got["items"]:
        assert row["canonical"] is not None and not row["not_found"]
        assert row["confidence"] >= 0.70
        assert row["is_weighed"] == (row["unit"] == "kg")
        if row["needs_confirmation"] and row["confidence"] < 0.75:
            assert row["candidates"], row  # the user chooses between real alternatives


@pytest.mark.db
def test_the_url_path_fetches_only_the_given_page(client, mvp_catalog, pages) -> None:
    r = client.post("/parse-recipe", json={"url": "https://recipes.example/hummus", "servings": 12})
    assert r.status_code == 200, r.text
    assert pages == ["https://recipes.example/hummus"]
    body = r.json()
    assert body["servings"] == 12
    chickpeas = next(i for i in body["items"] if i["canonical"]["display_name_he"] == "גרגרי חומוס יבשים")
    assert Decimal(chickpeas["quantity"]) == 1  # 4 cups = 800 g, still one 1 kg pack
    lemons = next(i for i in body["items"] if i["canonical"]["display_name_he"] == "לימונים")
    assert (Decimal(lemons["quantity"]), lemons["unit"]) == (Decimal("0.20"), "kg")
    r = client.post("/parse-recipe", json={"url": "https://recipes.example/missing"})
    assert r.status_code == 502


@pytest.mark.db
def test_servings_cannot_scale_a_recipe_without_a_yield(client, mvp_catalog) -> None:
    r = client.post("/parse-recipe", json={"text": "מצרכים:\n2 ק\"ג תפוחי אדמה", "servings": 6})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["servings"] is None and body["title"] is None
    assert [(i["canonical"]["display_name_he"], i["quantity"]) for i in body["items"]] == [("תפוחי אדמה", "2.00")]


@pytest.mark.db
def test_repeated_ingredients_are_merged(client, mvp_catalog) -> None:
    text = "מצרכים:\n6 ביצים\n1 כוס קמח\nלציפוי:\n8 ביצים\n1 כוס קמח"
    body = client.post("/parse-recipe", json={"text": text}).json()
    eggs = [i for i in body["items"] if i["canonical"]["display_name_he"] == "ביצים L"]
    assert len(eggs) == 1 and eggs[0]["quantity"] == "2"  # 14 eggs, packs of 12
    assert eggs[0]["input_text"] == "6 ביצים + 8 ביצים"


@pytest.mark.db
def test_request_validation(client) -> None:
    assert client.post("/parse-recipe", json={}).status_code == 422
    assert client.post("/parse-recipe", json={"text": "1 כוס קמח", "url": "https://x.example/r"}).status_code == 422
    assert client.post("/parse-recipe", json={"text": "1 כוס קמח", "servings": 0}).status_code == 422
    assert client.post("/parse-recipe", json={"text": "1 כוס קמח", "lang": "he"}).status_code == 422


@pytest.mark.db
def test_a_blocked_url_is_422_before_any_request(client, monkeypatch) -> None:
    def no_network(*args, **kwargs):
        raise AssertionError("no request may be sent")

    monkeypatch.setattr(httpx.Client, "stream", no_network)
    for url in ("http://127.0.0.1/recipe", "http://10.0.0.8/r", "http://[::1]/r", "http://localhost/r",
                "ftp://93.184.216.34/r", "http://user:pw@93.184.216.34/r", "http://93.184.216.34:8080/r",
                "http://169.254.169.254/latest/meta-data"):
        r = client.post("/parse-recipe", json={"url": url})
        assert r.status_code == 422, (url, r.text)


# --- the fetcher, with a mock transport ----------------------------------------------------------

PUBLIC = "http://93.184.216.34"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_check_url_accepts_public_addresses_only() -> None:
    check_url(f"{PUBLIC}/r")
    check_url("https://recipes.example/r", resolve=lambda host: ["93.184.216.34"])
    for addrs in (["127.0.0.1"], ["93.184.216.34", "192.168.1.4"], ["::ffff:10.0.0.1"], ["fe80::1"], []):
        with pytest.raises(FetchError) as err:
            check_url("https://recipes.example/r", resolve=lambda host, a=addrs: a)
        assert err.value.status == 422


def test_http_fetch_reads_a_page() -> None:
    html = "<html><body>מצרכים</body></html>"
    page = http_fetch(f"{PUBLIC}/r", _client(lambda req: httpx.Response(
        200, headers={"content-type": "text/html; charset=utf-8"}, content=html.encode())))
    assert page == html


def test_http_fetch_checks_every_redirect() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/r":
            return httpx.Response(302, headers={"location": "/r2"})
        if req.url.path == "/r2":
            return httpx.Response(301, headers={"location": "http://127.0.0.1/admin"})
        raise AssertionError("the private address was requested")

    with pytest.raises(FetchError) as err:
        http_fetch(f"{PUBLIC}/r", _client(handler))
    assert err.value.status == 422

    loop = _client(lambda req: httpx.Response(302, headers={"location": f"{PUBLIC}/again"}))
    with pytest.raises(FetchError, match="too many redirects"):
        http_fetch(f"{PUBLIC}/r", loop)


def test_http_fetch_refuses_large_bodies_other_types_and_errors() -> None:
    big = _client(lambda req: httpx.Response(200, headers={"content-type": "text/html"},
                                             content=b"x" * (MAX_BYTES + 1)))
    with pytest.raises(FetchError, match="larger than 2 MB"):
        http_fetch(f"{PUBLIC}/r", big)
    pdf = _client(lambda req: httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF"))
    with pytest.raises(FetchError, match="not a web page"):
        http_fetch(f"{PUBLIC}/r", pdf)
    gone = _client(lambda req: httpx.Response(404))
    with pytest.raises(FetchError) as err:
        http_fetch(f"{PUBLIC}/r", gone)
    assert err.value.status == 502

    def slow(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(FetchError, match="too long"):
        http_fetch(f"{PUBLIC}/r", _client(slow))
