"""Randomized correctness tests for basket pricing and /optimize through the real tables.

Each example is a small random world written to the database (2 chains, 3-5 stores at distinct
distances, 3-4 canonicals, base prices and store exceptions, items some chains or stores do not
stock, unit-price / percent / 1+1 / "N for X" promos, club-only promos, one "N for X" promo shared
by two products, a weighed canonical, items that state their pack count in the name: 2 to 12
units, with a typical pack of 1 to 6 units per canonical, so a line buys whole packs), priced by
the real precompute and served by the real
routes. The expected line of every (store, canonical) is recomputed here from the promo definitions
(``expected_line``) and the best plan from an exhaustive reference over the expected lines
(``exhaustive`` from test_api_optimizer_props.py), so neither shares code with basket.py or the
solvers. Seeds are fixed: a failure names its seed.

Invariants (docs/optimizer.md, "Invariants covered by tests"): lines equal the recomputed price;
totals are the sum of lines, rounded once to agorot; a store never prices what it does not stock;
a club deal is for members only; the heuristic equals the exhaustive optimum over lines priced one
by one (never better than the pooled one); the MILP equals the pooled optimum; the saving
breakdown is exactly basket saving minus travel minus extra stops, against the home store only;
``allow: []`` is omitting it; the response does not depend on the order of the list.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

import pytest
from api_world import EMB, World, add_price, add_promo, add_store
from psycopg.types.json import Jsonb
from test_api_optimizer_props import exhaustive

from smartcart_api import milp
from smartcart_api.embedding import to_pgvector
from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.settings import get_settings

D = Decimal
pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
SEEDS = range(18)
MANY_SEEDS = range(12)
FEW, MANY = (2, 6), (8, 14)  # promos drawn per world
PACK_EFFECT_SEEDS: set[int] = set()  # seeds with a line whose shelf packs differ from the quantity
CLUBS = ("club-a", "club-b")


def m2(x: Decimal) -> Decimal:
    return x.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def m4(x: Decimal) -> Decimal:
    return x.quantize(D("0.0001"), rounding=ROUND_HALF_UP)


# --- the world and its independent price model ---------------------------------------------------


@dataclass
class Promo:
    label: str
    chain: str
    store: int | None  # None: chain-wide
    kind: str  # price | percent | bogo | bogo_pct (buy 1, get 1 at value % off) | bundle
    value: Decimal | None
    n: int | None
    club: str | None
    items: set[int]  # canonical ids it covers (at this promo's chain)


@dataclass
class Built:
    stores: list[dict]  # id, chain, km
    canon: dict[int, bool]  # canonical id -> weighed
    shelf: dict[tuple[int, int], Decimal] = field(default_factory=dict)  # (store, canon) -> price
    sub_shelf: dict[tuple[int, int], Decimal] = field(default_factory=dict)  # close-level item
    sibling: dict[int, int] = field(default_factory=dict)  # canonical -> its fat_pct sibling
    per: dict[int, int] = field(default_factory=dict)  # canonical -> units in one requested pack
    pack_n: dict[tuple[str, int], int] = field(default_factory=dict)  # (chain, canon) -> units/item
    promos: list[Promo] = field(default_factory=list)
    home: int | None = None


def fold(shelf: Decimal, p: Promo) -> tuple[Decimal, int] | None:
    """(price of one pack under the promo, packs needed) by the table in precompute.py, or None
    when the promo would not lower the price."""
    if p.kind == "price":
        eff, need = p.value, p.n or 1
    elif p.kind == "percent":
        eff, need = shelf * (1 - p.value / 100), p.n or 1
    elif p.kind == "bogo":
        eff, need = shelf / 2, 2
    elif p.kind == "bogo_pct":  # "the second at P %": pay 1 + (1 - P/100) shelf prices for 2 packs
        eff, need = shelf * (2 - p.value / 100) / 2, 2
    else:  # bundle: N for X; a value below one shelf price is a price per unit
        eff, need = (p.value if p.value < shelf else p.value / p.n), p.n
    eff = m4(eff)
    return (eff, need) if 0 <= eff < shelf else None


def line_price(
    shelf: Decimal, offer: tuple[Decimal, int, Promo | None], qty: Decimal, weighed: bool
) -> Decimal:
    eff, need, promo = offer
    if weighed:
        return m2(qty * eff)
    if promo is None:
        return m2(qty * shelf)
    if need <= 1:
        return m2(qty * eff)
    bundles = (qty / need).to_integral_value(rounding=ROUND_FLOOR)
    return m2(bundles * m2(eff * need) + (qty - bundles * need) * shelf)


@dataclass
class Best:
    eff: Decimal  # price per pack (per kg when weighed) of the chosen offer
    kind: str  # main (any-brand item, maybe on promo) | sub (close-level item, no promo)
    shelf: Decimal
    n: int | None = None  # units in one shelf item, when its name states them


@dataclass
class Way:
    """One way to buy a canonical at a store: an item and one of its offers open to the user."""

    sub: bool  # the close-level substitute item
    shelf: Decimal
    n: int | None  # units in one shelf item, when its name states them
    offer: tuple[Decimal, int, Promo | None]  # price per pack, packs needed, promo


def packs_of(b: Best | Way, qty: Decimal, per: int | None) -> Decimal:
    """Shelf items that cover ``qty`` requested packs of ``per`` units each (whole packs), or the
    quantity itself when the item states no count or the canonical is weighed."""
    if b.n is None or per is None:
        return qty
    return (qty * per / b.n).to_integral_value(rounding=ROUND_CEILING)


def ways_at(built: Built, store: dict, cid: int, flex: str, clubs: list[str]) -> list[Way]:
    """Every way the store sells canonical ``cid`` to this user for flexibility ``flex``: the
    any-brand item at its shelf price and under each promo that lowers it (a club promo only for
    members), and at "close" the substitute item at its shelf price. Independent of the precompute:
    nothing here is ranked by unit price."""
    sid = store["id"]
    n = built.pack_n.get((store["chain"], cid))
    out: list[Way] = []
    if (sid, cid) in built.shelf:
        shelf = built.shelf[(sid, cid)]
        out.append(Way(False, shelf, n, (shelf, 1, None)))
        for p in built.promos:
            if p.chain != store["chain"] or cid not in p.items or p.store not in (None, sid):
                continue
            if p.club is not None and p.club not in clubs:
                continue
            f = fold(shelf, p)
            if f is not None:
                out.append(Way(False, shelf, n, (f[0], f[1], p)))
    if flex == "close" and (sid, cid) in built.sub_shelf:
        price = built.sub_shelf[(sid, cid)]
        out.append(Way(True, price, n, (price, 1, None)))
    return out


@dataclass
class Pick:
    way: Way
    total: Decimal
    ambiguous: bool  # another offer of the same price, kind of item and unit price differs in shape


def cheapest(ways: list[Way], qty: Decimal, per: int | None, weighed: bool) -> Pick | None:
    """The cheapest line for ``qty``; a tie goes to an any-brand item over a substitute, then to
    the lower price per pack (the best unit price, which is what the precompute ranks by)."""
    if not ways:
        return None

    def total(w: Way) -> Decimal:
        return line_price(w.shelf, w.offer, packs_of(w, qty, per), weighed)

    def key(w: Way) -> tuple:
        return (total(w), w.sub, w.offer[0])

    best = min(ways, key=key)
    tied = {
        (w.sub, w.offer[2].label if w.offer[2] else None, w.offer[1])
        for w in ways
        if key(w) == key(best)
    }
    return Pick(best, total(best), len(tied) > 1)


@dataclass
class Exp:
    totals: set[Decimal]  # the line total (a set of one: kept for the callers that test membership)
    sub: bool
    src: int  # the canonical whose item is bought (a sibling's, when allowed and cheaper)
    best: Best
    orig: set[Decimal] | None  # a substitute's original_here totals, None when the store has none
    offer: tuple  # the offer the line charges
    ambiguous: bool = False  # two offers tie in price and differ in shape (a promo, a bundle size)


def expected(built: Built, store: dict, item: dict, clubs: list[str]) -> Exp | None:
    """What the line for ``item`` at ``store`` must be, or None when the store cannot supply it.

    The cheapest line for the quantity among every offer open to the user (docs/optimizer.md,
    "Offers for the quantity asked"), not the offer with the best unit price."""
    cid, flex = item["canonical_id"], item.get("flex_level", "any_brand")
    qty, weighed = D(item["quantity"]), built.canon[cid]
    per = built.per.get(cid)
    own = cheapest(ways_at(built, store, cid, flex, clubs), qty, per, weighed)
    src, chosen = cid, own
    sib_cid = built.sibling.get(cid)
    if item.get("allow") and sib_cid is not None:
        sib = cheapest(ways_at(built, store, sib_cid, flex, clubs), qty, per, weighed)
        # The allowed sibling is bought when it is cheaper for the quantity; the own offer keeps a tie.
        if sib is not None and (own is None or sib.total < own.total):
            src, chosen = sib_cid, sib
    if chosen is None:
        return None
    w = chosen.way
    sub = src != cid or w.sub
    orig = None
    if sub:
        o = cheapest(ways_at(built, store, cid, "any_brand", clubs), qty, per, weighed)
        if o is not None:
            orig = {o.total}
    best = Best(w.offer[0], "sub" if w.sub else "main", w.shelf, w.n)
    return Exp({chosen.total}, sub, src, best, orig, w.offer, chosen.ambiguous)


def build_world(
    db,
    rnd: random.Random,
    w: World,
    prnd: random.Random | None = None,
    promos: tuple[int, int] = FEW,
) -> Built:
    """``prnd`` draws the pack features (typical pack of a canonical, units in a chain's item), so
    the rest of every world is the same with or without them."""
    prnd = prnd or random.Random(0)
    n_stores = rnd.randint(3, 5)
    kms = [k / 10 for k in rnd.sample(range(10, 46), n_stores)]
    stores = []
    for n, km in enumerate(sorted(kms)):
        chain = w.chains[rnd.randrange(2)]
        stores.append({"id": add_store(db, chain, f"R{n}", km), "chain": chain, "km": km})
    for ch in w.chains:  # every chain has at least one store
        if not any(s["chain"] == ch for s in stores):
            stores[-1]["chain"] = ch
            db.execute("UPDATE stores SET chain_id = %s WHERE id = %s", (ch, stores[-1]["id"]))
    emb = to_pgvector(EMB.embed_one("מוצר"))
    n_canon = rnd.randint(3, 4)
    built = Built(stores=stores, canon={})
    items: dict[tuple[str, int], int] = {}
    drawn: dict[tuple[str, int], int | None] = {}

    def units_in(ch: str, cid: int) -> int | None:
        """Units the chain's item of the canonical states in its name, None when it states none.
        The main and the substitute item of one chain share it."""
        if built.canon[cid]:
            return None
        if (ch, cid) not in drawn:
            drawn[(ch, cid)] = prnd.choice([None, None, 2, 3, 4, 6, 12])
            if drawn[(ch, cid)]:
                built.pack_n[(ch, cid)] = drawn[(ch, cid)]
        return drawn[(ch, cid)]

    def item_name(label: str, cid: int, n: int | None) -> str:
        # A pack count is the only number in these names (digits are read as sizes).
        return f"{label} {cid}" if n is None else f"{label} {'אבגדהוז'[cid % 7]} {n} יח'"

    milk_pair = rnd.random() < 0.5  # canonicals 0 and 1: the same milk at 3 % and at 1 %
    for c in range(n_canon):
        weighed = c == n_canon - 1 and rnd.random() < 0.5
        milk = milk_pair and c < 2
        cid = db.execute(
            "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type,"
            " base_unit, critical_attrs, soft_attrs, embedding, is_mvp, rank)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, true, %s) RETURNING id",
            (
                "t.dairy.milk" if milk else "t.snacks.wafer",
                f"rnd-{c}",
                f"מוצר {c}",
                "t_milk" if milk else "t_wafer",
                "kg" if weighed else "unit",
                Jsonb({"fat_pct": 3 if c == 0 else 1} if milk else {}),
                Jsonb({"brand": None} if milk else {}),
                emb,
                50 + c,
            ),
        ).fetchone()[0]
        built.canon[cid] = weighed
        if not weighed:
            built.per[cid] = 1
            if not milk and prnd.random() < 0.6:
                built.per[cid] = prnd.choice([2, 3, 4, 6])
                db.execute(
                    "UPDATE canonical_products SET soft_attrs = %s WHERE id = %s",
                    (Jsonb({"pack_size": built.per[cid], "unit": "unit"}), cid),
                )
        if milk and c == 1:
            first = next(iter(built.canon))
            built.sibling[cid], built.sibling[first] = first, cid
        for ch in w.chains:
            style = rnd.choices(["all", "some", "none"], [6, 3, 1])[0]
            mine = [s for s in stores if s["chain"] == ch]
            if style == "none" or not mine:
                continue
            n = units_in(ch, cid)
            iid = db.execute(
                "INSERT INTO items (chain_id, item_code, raw_name, quantity, unit, is_weighed)"
                " VALUES (%s, %s, %s, 1, %s, %s) RETURNING id",
                (ch, f"r{c}", item_name("מוצר", c, n), 'ק"ג' if weighed else "יחידה", weighed),
            ).fetchone()[0]
            items[(ch, cid)] = iid
            db.execute(
                "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
                " VALUES (%s, %s, 'any_brand', 0.97, 'rule')",
                (iid, cid),
            )
            base = D(rnd.randint(1000, 9000) if weighed else rnd.randint(300, 1500)) / 100
            uom, est = ("kg", True) if weighed else (None, False)
            if style == "all":
                add_price(
                    db, iid, None, str(base), str(base) if weighed else None, uom, w.valid_from, est
                )
                for s in mine:
                    over = base
                    if rnd.random() < 0.3:
                        over = D(round(base * D(rnd.randint(80, 125)) * 100) // 100) / 100
                        add_price(
                            db,
                            iid,
                            s["id"],
                            str(over),
                            str(over) if weighed else None,
                            uom,
                            w.valid_from,
                            est,
                        )
                    built.shelf[(s["id"], cid)] = over
            else:
                for s in rnd.sample(mine, rnd.randint(1, len(mine))):
                    p = D(round(base * D(rnd.randint(85, 115)))) / 100
                    add_price(
                        db,
                        iid,
                        s["id"],
                        str(p),
                        str(p) if weighed else None,
                        uom,
                        w.valid_from,
                        est,
                    )
                    built.shelf[(s["id"], cid)] = p

    # A close-level substitute item (no promo) in most chains for canonicals outside the milk pair.
    for cid in built.canon:
        if cid in built.sibling:
            continue
        for ch in w.chains:
            mine = [s for s in stores if s["chain"] == ch]
            if not mine or rnd.random() < 0.4:
                continue
            weighed = built.canon[cid]
            n = units_in(ch, cid)
            iid = db.execute(
                "INSERT INTO items (chain_id, item_code, raw_name, quantity, unit, is_weighed)"
                " VALUES (%s, %s, %s, 1, %s, %s) RETURNING id",
                (
                    ch,
                    f"sub{cid}",
                    item_name("תחליף", cid, n),
                    'ק"ג' if weighed else "יחידה",
                    weighed,
                ),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
                " VALUES (%s, %s, 'close', 0.8, 'rule')",
                (iid, cid),
            )
            price = D(rnd.randint(900, 9500) if weighed else rnd.randint(250, 1600)) / 100
            add_price(
                db,
                iid,
                None,
                str(price),
                str(price) if weighed else None,
                "kg" if weighed else None,
                w.valid_from,
                weighed,
            )
            for s in mine:
                built.sub_shelf[(s["id"], cid)] = price

    def add(label, ch, store, kind, value, n, club, cids, desc):
        covered = [items[(ch, c)] for c in cids if (ch, c) in items]
        if not covered:
            return
        add_promo(
            db,
            ch,
            store,
            label,
            covered,
            {
                "price": "price",
                "percent": "percent",
                "bogo": "buy_x_get_y",
                "bogo_pct": "buy_x_get_y",
                "bundle": "bundle",
            }[kind],
            "1" if kind == "bogo_pct" else (None if value is None else str(value)),
            None if n is None or kind in ("bogo", "bogo_pct") else str(n),
            club_only=club is not None,
            club_name=club,
            description=desc,
            get_percent=str(value) if kind == "bogo_pct" else None,
        )
        built.promos.append(
            Promo(label, ch, store, kind, value, n, club, {c for c in cids if (ch, c) in items})
        )

    for k in range(rnd.randint(*promos)):
        ch = w.chains[rnd.randrange(2)]
        cid = rnd.choice(list(built.canon))
        weighed = built.canon[cid]
        kind = rnd.choice(
            ["price", "percent"]
            if weighed
            else ["price", "percent", "bogo", "bogo_pct", "bundle", "bundle"]
        )
        mine = [s for s in stores if s["chain"] == ch]
        store = rnd.choice([None, None, rnd.choice(mine)["id"]]) if mine else None
        club = rnd.choice([None, None, CLUBS[0], CLUBS[1]])
        ref = max((built.shelf.get((s["id"], cid), D(1)) for s in mine), default=D(5))
        n = rnd.randint(2, 4)
        value = {
            "price": m2(ref * D(rnd.randint(55, 95)) / 100),
            "percent": D(rnd.randint(5, 40)),
            "bogo": None,
            "bogo_pct": D(rnd.choice([25, 50, 75])),
            "bundle": m2(ref * n * D(rnd.randint(60, 95)) / 100),
        }[kind]
        if kind in ("price", "percent"):
            n = rnd.choice([None, None, 2, 3])  # a minimum quantity
        add(f"P{k}", ch, store, kind, value, n, club, [cid], f"מבצע {k}")
    # One "N for X" shared by two products of a chain (the MILP pools its units).
    plain = [c for c, wd in built.canon.items() if not wd]
    ch = w.chains[rnd.randrange(2)]
    pair = [c for c in plain if (ch, c) in items]
    if len(pair) >= 2 and rnd.random() < 0.8:
        a, b = rnd.sample(pair, 2)
        mine = [s for s in stores if s["chain"] == ch]
        n = rnd.randint(2, 3)
        shelves = [
            built.shelf[(s["id"], c)] for s in mine for c in (a, b) if (s["id"], c) in built.shelf
        ]
        if shelves:
            x = max(max(shelves), m2(n * min(shelves) * D(rnd.randint(60, 90)) / 100))
            add("SH", ch, None, "bundle", x, n, None, [a, b], f"{n} ב-{x}")
    built.home = rnd.choice(stores)["id"] if rnd.random() < 0.85 else None
    return built


def pooled_problem(
    built: Built,
    items: list[dict],
    clubs: list[str],
    trips: dict[int, Decimal],
    extra: Decimal,
) -> milp.Problem | None:
    """The exhaustive reference's input: the expected line of every (store, need), with the
    "N for X" lines of one promo and store in one group. None when a tie makes the line ambiguous
    (the generator rarely makes one)."""
    lines, groups = [], {}
    for s in built.stores:
        for it in items:
            cid, q = it["canonical_id"], D(it["quantity"])
            exp = expected(built, s, it, clubs)
            if exp is None:
                continue
            if exp.ambiguous:
                return None
            eff, need, promo = exp.offer
            key = None
            if promo is not None and need > 1 and not built.canon[cid]:
                # Every promo that needs several packs pools the packs of the lines that buy
                # under it (two needs can map to the same item, or two products share the promo).
                key = f"{promo.label}@{s['id']}"
                group = groups.setdefault(
                    key, milp.Group(key, s["id"], promo.label, need, m2(eff * need), {}, None)
                )
                if group.fixed != m2(eff * need):
                    return None  # members at different bundle prices: not a case modelled here
                group.unit[cid] = D(0)
            lines.append(
                milp.Line(
                    cid,
                    s["id"],
                    cid * 1000 + s["id"],
                    next(iter(exp.totals)),
                    exp.best.shelf,
                    int(packs_of(exp.best, q, built.per.get(cid))) if key else None,
                    key,
                    exp.sub,
                )
            )
    stores = [milp.StoreCost(s["id"], trips[s["id"]], n) for n, s in enumerate(built.stores)]
    return milp.Problem([i["canonical_id"] for i in items], stores, lines, groups, extra)


def trip(s: dict, dist_m: int, travel: dict) -> Decimal:
    if travel["mode"] == "car":
        return m2(D(dist_m) / 1000 * D(travel["cost_per_km"]) * 2)
    if travel["mode"] == "walk_transit":
        return m2(get_settings().walk_transit_cost_per_store)
    return D(0)


# --- running an example -----------------------------------------------------------------------------


TRAVELS = [
    {"mode": "car", "cost_per_km": "1.2", "extra_stop_value": "25"},
    {"mode": "car", "cost_per_km": "0.3", "extra_stop_value": "2"},
    {"mode": "car", "cost_per_km": "0", "extra_stop_value": "0"},
    {"mode": "walk_transit", "extra_stop_value": "5"},
    {"mode": "delivery", "extra_stop_value": "0"},
]


def money_ok(v: str) -> Decimal:
    d = D(v)
    assert d == m2(d), f"not whole agorot: {v}"
    return d


def strip(obj):
    """A response without its timestamp and with list orders that follow the request removed."""
    if isinstance(obj, dict):
        out = {k: strip(v) for k, v in obj.items() if k != "generated_at"}
        for k in ("missing", "item_ids"):
            if k in out:
                out[k] = sorted(out[k])
        if isinstance(out.get("items"), list):
            out["items"] = sorted(out["items"], key=lambda i: i["canonical_id"])
        return out
    if isinstance(obj, list):
        return [strip(v) for v in obj]
    return obj


@pytest.fixture
def base(db, catalog: World) -> World:
    for ch in catalog.chains:
        db.execute("INSERT INTO chains (id, name, portal) VALUES (%s, %s, 'other')", (ch, ch))
    db.execute("SELECT ensure_price_partition(%s::date)", (catalog.valid_from.date(),))
    return catalog


def example(db, base: World, seed: int, promos: tuple[int, int] = FEW):
    rnd = random.Random(seed)
    built = build_world(db, rnd, base, random.Random(seed + 7919), promos)
    precompute_effective_prices(db, chains=base.chains)
    cids = list(built.canon)
    items = []
    for cid in rnd.sample(cids, rnd.randint(2, len(cids))):
        q = D(rnd.randint(1, 9)) / 4 if built.canon[cid] else D(rnd.randint(1, 5))
        item = {"canonical_id": cid, "quantity": str(q)}
        if rnd.random() < 0.4:
            item["flex_level"] = rnd.choice(["any_brand", "close", "close"])
        if cid in built.sibling and rnd.random() < 0.6:
            item["allow"] = ["fat_pct"]
        items.append(item)
    clubs = rnd.choice([[], [CLUBS[0]], [CLUBS[1]], list(CLUBS)])
    loc = base.location
    body = {"items": items, "location": loc, "clubs": clubs}
    if built.home is not None:
        body["home_store_id"] = built.home
    return rnd, built, items, clubs, body


@pytest.mark.parametrize("seed", SEEDS)
def test_compare_prices_equal_an_independent_recomputation(
    db, client, base: World, seed: int
) -> None:
    check_compare(db, client, base, seed, FEW)


@pytest.mark.parametrize("seed", MANY_SEEDS)
def test_compare_prices_with_many_promos_equal_an_independent_recomputation(
    db, client, base: World, seed: int
) -> None:
    """Eight to fourteen promos over the same few canonicals: several per item and chain, so a
    key has more candidate offers than the table keeps unless they are the useful ones. The line is
    still the cheapest for the quantity among every offer open to the user (``ways_at``)."""
    check_compare(db, client, base, seed, MANY)
    n = db.execute(
        "SELECT max(c) FROM (SELECT count(*) c FROM effective_offers GROUP BY canonical_id, store_id, flex_level) q"
    ).fetchone()[0]
    assert n is None or n <= 4  # at most four rows next to the effective_prices row


def check_compare(db, client, base: World, seed: int, promos: tuple[int, int]) -> None:
    rnd, built, items, clubs, body = example(db, base, seed, promos)
    qty = {i["canonical_id"]: D(i["quantity"]) for i in items}
    by_item = {i["canonical_id"]: i for i in items}
    by_id = {s["id"]: s for s in built.stores}
    r = client.post("/compare", json=body)
    assert r.status_code == 200, r.text
    resp = r.json()
    seen = set()
    for st in resp["stores"]:
        seen.add(st["store_id"])
        s = by_id[st["store_id"]]
        exp = {c: expected(built, s, by_item[c], clubs) for c in qty}
        have = {c for c, e in exp.items() if e is not None}
        # A store prices exactly what it stocks, lists the rest as missing, and is never dropped
        # from the list of lines silently.
        assert {i["canonical_id"] for i in st["items"]} == have
        assert sorted(st["missing"]) == sorted(set(qty) - have)
        assert st["found_count"] == len(have)
        total = D(0)
        for li in st["items"]:
            cid = li["canonical_id"]
            got = money_ok(li["line_total"])
            e = exp[cid]
            assert got in e.totals, (seed, s["id"], cid)
            assert D(li["quantity"]) == qty[cid]
            # Whole shelf packs cover the quantity asked; the total is built on them.
            assert D(li["packs"]) == packs_of(e.best, qty[cid], built.per.get(cid)), (seed, cid)
            assert (li["pack_units"] is None) == (e.best.n is None)
            assert e.best.n is None or D(li["pack_units"]) == e.best.n
            if D(li["packs"]) != qty[cid]:
                PACK_EFFECT_SEEDS.add(seed)
            # Substitutes are labeled, with the original's offer at the same store; others never.
            assert li["is_substitute"] == e.sub, (seed, s["id"], cid)
            assert (li["original_here"] is not None) == (e.orig is not None), (seed, s["id"], cid)
            if e.orig is not None:
                assert D(li["original_here"]["line_total"]) in e.orig
                assert li["original_item_id"] == li["original_here"]["item_id"] != li["item_id"]
            else:
                assert li["original_item_id"] is None
            if e.src != cid:  # a sibling's item: the allowed attribute is tagged as differing
                assert {"key": "fat_pct", "status": "differs"} in [
                    {"key": t["key"], "status": t["status"]} for t in li["tags"]
                ]
            total += got
            # A club deal is never applied to a non-member, and never counted in the total.
            if li["club_required"]:
                assert li["club_name"] in clubs
            if li["club_offer_discount"] is not None:
                assert D(li["club_offer_discount"]) > 0 and li["club_offer_name"] not in clubs
        assert money_ok(st["total"]) == m2(total)
        assert st["total"] == str(m2(total))
    assert seen == {
        s["id"] for s in built.stores if any(expected(built, s, i, clubs) for i in items)
    }
    # saving_vs_home: over the canonicals both stores supply, positive means cheaper.
    if built.home is not None:
        stores = {st["store_id"]: st for st in resp["stores"]}
        if built.home in stores:
            home = {i["canonical_id"]: D(i["line_total"]) for i in stores[built.home]["items"]}
            for st in stores.values():
                common = [i for i in st["items"] if i["canonical_id"] in home]
                want = m2(sum((home[i["canonical_id"]] - D(i["line_total"]) for i in common), D(0)))
                assert D(st["saving_vs_home"]) == want
            assert resp["home_store_total"] == stores[built.home]["total"]
        else:  # documented: the home store's total over what it supplies, 0.00 when nothing
            assert resp["home_store_total"] == "0.00"
    # Non-members never pay less than members, the total only goes down with a club.
    if clubs:
        nomember = client.post("/compare", json={**body, "clubs": []}).json()
        a = {st["store_id"]: D(st["total"]) for st in resp["stores"]}
        for st in nomember["stores"]:
            assert D(st["total"]) >= a[st["store_id"]], (seed, st["store_id"])


def test_the_random_worlds_exercise_pack_rounding() -> None:
    """The comparison above must really meet lines whose shelf packs differ from the quantity
    (it runs before this test in the file; run alone it has seen nothing and is skipped)."""
    if not PACK_EFFECT_SEEDS:
        pytest.skip("run together with test_compare_prices_equal_an_independent_recomputation")
    assert len(PACK_EFFECT_SEEDS) >= len(SEEDS) // 3, sorted(PACK_EFFECT_SEEDS)


@pytest.mark.parametrize("seed", SEEDS)
def test_optimize_plans_equal_the_exhaustive_reference(db, client, base: World, seed: int) -> None:
    check_optimize(db, client, base, seed, FEW)


@pytest.mark.parametrize("seed", MANY_SEEDS)
def test_optimize_plans_with_many_promos_equal_the_exhaustive_reference(
    db, client, base: World, seed: int
) -> None:
    check_optimize(db, client, base, seed, MANY)


def check_optimize(db, client, base: World, seed: int, promos: tuple[int, int]) -> None:
    rnd, built, items, clubs, body = example(db, base, seed, promos)
    qty = {i["canonical_id"]: D(i["quantity"]) for i in items}
    cmp = {st["store_id"]: st for st in client.post("/compare", json=body).json()["stores"]}
    dist = {
        sid: d
        for sid, d in db.execute(
            "SELECT id, round(ST_Distance(geog, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography))::int"
            " FROM stores WHERE id = ANY(%s)",
            (base.location["lon"], base.location["lat"], [s["id"] for s in built.stores]),
        )
    }
    assert all(dist[sid] == st["distance_m"] for sid, st in cmp.items())
    travel = rnd.choice(TRAVELS)
    k = rnd.randint(1, 3)
    mss = rnd.choice(["0", "0", "3", "25"])
    extra = D(travel["extra_stop_value"])
    trips = {s["id"]: trip(s, dist.get(s["id"], 0), travel) for s in built.stores}
    problem = pooled_problem(built, items, clubs, trips, extra)
    req = {**body, "max_stores": k, "travel": travel, "min_split_saving": mss}
    heur = client.post("/optimize", json=req).json()
    mil = client.post("/optimize", json={**req, "solver": "milp"}).json()
    assert heur["solver"] == "heuristic" and mil["solver"] == "milp"

    def cost(plan: dict) -> Decimal:
        n = len(plan["stores"])
        return D(plan["total"]) + D(plan["travel_cost"]) + extra * max(0, n - 1)

    for resp in (heur, mil):
        for kind in ("single", "split", "minimum_effort"):
            plan = resp[kind]
            if plan is None:
                continue
            # Totals are the sum of the lines; the plan covers each need once or lists it missing.
            seen: list[int] = []
            for a in plan["stores"]:
                st = a["store"]
                assert money_ok(st["total"]) == m2(
                    sum((D(i["line_total"]) for i in st["items"]), D(0))
                )
                assert sorted(a["item_ids"]) == sorted(i["item_id"] for i in st["items"])
                seen += [i["canonical_id"] for i in st["items"]]
            assert money_ok(plan["total"]) == m2(
                sum((D(a["store"]["total"]) for a in plan["stores"]), D(0))
            )
            assert sorted([*seen, *plan["missing"]]) == sorted(qty), (seed, kind)
            assert len(set(seen)) == len(seen)
            assert len(plan["stores"]) <= (1 if kind != "split" else k)
            by_item = {i["canonical_id"]: i for i in items}
            for a in plan["stores"]:
                store = next(s for s in built.stores if s["id"] == a["store"]["store_id"])
                for i in a["store"]["items"]:
                    assert expected(built, store, by_item[i["canonical_id"]], clubs) is not None
            # The saving breakdown, against the home store only.
            bd = plan["breakdown"]
            assert (bd is None) == (built.home is None)
            if bd is not None:
                for f in bd:
                    money_ok(bd[f])
                assert D(bd["net_saving"]) == D(bd["basket_saving"]) - D(bd["travel_cost"]) - D(
                    bd["extra_stop_cost"]
                )
                assert D(bd["travel_cost"]) >= 0 and D(bd["extra_stop_cost"]) == extra * max(
                    0, len(plan["stores"]) - 1
                )
                home_trip = trips[built.home]
                bought = [a for a in plan["stores"] if a["store"]["items"]]
                visited = sum((trips[a["store"]["store_id"]] for a in bought), D(0))
                assert D(plan["travel_cost"]) == m2(visited)
                want_travel = max(D(0), visited - home_trip) if bought else D(0)
                assert D(bd["travel_cost"]) == m2(want_travel)
                # Each store of the plan shows the saving of the lines bought there.
                assert sum((D(a["store"]["saving_vs_home"]) for a in plan["stores"]), D(0)) == D(
                    bd["basket_saving"]
                )
        # The minimum-effort plan is the home store alone and saves nothing against itself.
        me = resp["minimum_effort"]
        assert (me is None) == (built.home is None)
        if me is not None:
            assert [a["store"]["store_id"] for a in me["stores"]] in ([built.home], [])
            assert (
                D(me["breakdown"]["net_saving"]) == 0 and D(me["breakdown"]["basket_saving"]) == 0
            )
        # Net saving matches a recomputation from the expected lines (heuristic: lines alone).
        if built.home is not None and resp is heur and built.home in cmp:
            home_lines = {i["canonical_id"]: D(i["line_total"]) for i in cmp[built.home]["items"]}
            for kind in ("single", "split"):
                plan = resp[kind]
                if plan is None:
                    continue
                basket = D(0)
                for a in plan["stores"]:
                    for i in a["store"]["items"]:
                        if i["canonical_id"] in home_lines:
                            basket += home_lines[i["canonical_id"]] - D(i["line_total"])
                bd = plan["breakdown"]
                assert D(bd["basket_saving"]) == m2(basket)
                if D(bd["net_saving"]) > 0:
                    assert basket - D(bd["travel_cost"]) - D(bd["extra_stop_cost"]) > 0
    # Optimum checks against the exhaustive reference.
    if problem is None:
        return
    alone = exhaustive(problem, k, pool=False)
    pooled = exhaustive(problem, k)
    best = heur["split"] or heur["single"]
    one = exhaustive(problem, 1, pool=False)
    # single is the best one-store plan, as priced line by line.
    assert (len(heur["single"]["missing"]), cost(heur["single"])) == (one[0], D(one[1]) / 100), seed
    if heur["split"] is not None:
        assert cost(heur["single"]) - cost(heur["split"]) >= D(mss)
        assert len(heur["split"]["missing"]) <= len(heur["single"]["missing"])
    # With min_split_saving 0 the plan shown is the optimum, unless the optimum completes a list
    # that no single store completes at a higher cost: a split is shown only when it saves at
    # least min_split_saving over single (docs/optimizer.md, "Plans"; a design choice).
    if mss == "0" and alone[0] == one[0]:
        assert (len(best["missing"]), cost(best)) == (alone[0], D(alone[1]) / 100), (seed, k)
    # The heuristic is never better than the pooled optimum; the MILP is the pooled optimum.
    assert (len(best["missing"]), cost(best)) >= (pooled[0], D(pooled[1]) / 100)
    mbest = mil["split"] or mil["single"]
    one_pooled = exhaustive(problem, 1)
    if mss == "0" and pooled[0] == one_pooled[0]:
        assert (len(mbest["missing"]), cost(mbest)) == (pooled[0], D(pooled[1]) / 100), (seed, k)
    assert (len(mil["single"]["missing"]), cost(mil["single"])) == (
        one_pooled[0],
        D(one_pooled[1]) / 100,
    )
    assert (len(mbest["missing"]), cost(mbest)) <= (len(best["missing"]), cost(best))


@pytest.mark.parametrize("seed", SEEDS[:12])
def test_response_does_not_depend_on_the_order_of_the_list_and_empty_allow_is_omitting_it(
    db, client, base: World, seed: int
) -> None:
    rnd, built, items, clubs, body = example(db, base, seed)
    travel = rnd.choice(TRAVELS)
    shuffled = copy.deepcopy(items)
    rnd.shuffle(shuffled)
    with_allow = [{**i, "allow": i.get("allow", [])} for i in items]
    explicit = [{**i, "flex_level": i.get("flex_level", "any_brand")} for i in items]
    for path, extra in (
        ("/compare", {}),
        ("/optimize", {"travel": travel, "min_split_saving": "0"}),
        ("/optimize", {"travel": travel, "solver": "milp", "min_split_saving": "0"}),
    ):
        ref = strip(client.post(path, json={**body, **extra}).json())
        for variant in (shuffled, with_allow, explicit, list(reversed(with_allow))):
            got = client.post(path, json={**body, "items": variant, **extra})
            assert got.status_code == 200
            assert strip(got.json()) == ref, (seed, path)
    # The same quantity split over two entries is one line.
    if items[0]["quantity"] != "1" and "." not in items[0]["quantity"]:
        q = int(items[0]["quantity"])
        split = [{**items[0], "quantity": "1"}, {**items[0], "quantity": str(q - 1)}, *items[1:]]
        for path in ("/compare", "/optimize"):
            a = strip(client.post(path, json=body).json())
            b = strip(client.post(path, json={**body, "items": split}).json())
            assert a == b, (seed, path)
