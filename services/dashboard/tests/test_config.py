from smartcart_dashboard.config import PHASE0_CHAINS, resolve_dsn


def test_phase0_chains_match_d13():
    assert len(PHASE0_CHAINS) == 10
    assert [c.name for c in PHASE0_CHAINS if c.main] == [
        "Shufersal",
        "Rami Levy",
        "Victory",
        "Yeinot Bitan and Carrefour",
        "Hazi Hinam",
        "Tiv Taam",
    ]
    ids = [i for c in PHASE0_CHAINS for i in c.chain_ids]
    assert len(ids) == len(set(ids)) == 12


def test_readonly_url_preferred_without_warning():
    conn = resolve_dsn({"DATABASE_URL_READONLY": "postgresql://ro@h/db", "DATABASE_URL": "x"})
    assert conn.dsn == "postgresql://ro@h/db"
    assert conn.warning is None


def test_fallback_to_database_url_warns():
    conn = resolve_dsn({"DATABASE_URL": "postgresql://rw@h/db", "DATABASE_URL_READONLY": " "})
    assert conn.dsn == "postgresql://rw@h/db"
    assert "read" in conn.warning.lower() and "smartcart_readonly" in conn.warning


def test_no_database_configured():
    assert resolve_dsn({}) is None
