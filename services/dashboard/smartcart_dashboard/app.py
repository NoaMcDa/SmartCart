"""Internal ingestion dashboard (issue #46). Run from the repo root:

    uv run streamlit run services/dashboard/smartcart_dashboard/app.py

Read-only: the connection comes from DATABASE_URL_READONLY (fallback DATABASE_URL, with a
warning), is opened read-only, and only the SELECTs in ``queries`` are ever run.
"""

from __future__ import annotations

import pandas as pd
import psycopg
import streamlit as st

from smartcart_dashboard import queries
from smartcart_dashboard.config import PHASE0_CHAINS, STALE_AFTER_HOURS, resolve_dsn

FLAG_TEXT = {
    "ok": "ok",
    "stale": f"STALE: no load in {STALE_AFTER_HOURS}h",
    "missing": "MISSING: no data at all",
}
RED = "background-color: #f8d7da; color: #58151c"


def _connect(dsn: str) -> psycopg.Connection:
    conn = psycopg.connect(dsn, connect_timeout=10)
    conn.read_only = True  # the server rejects any write on this connection
    return conn


@st.cache_data(ttl=60, show_spinner="Reading the database")
def _load(dsn: str, sha_query: str) -> dict:
    with _connect(dsn) as conn:
        data = {
            "overview": queries.chain_overview(conn),
            "failed": queries.failed_files(conn),
            "file_counts": queries.file_counts(conn),
            "quarantine_counts": queries.quarantine_counts(conn),
            "sha_matches": queries.file_by_sha256(conn, sha_query) if sha_query else [],
        }
        conn.rollback()
    return data


def _flag_rows(row: pd.Series) -> list[str]:
    return [RED if row["flag"] != FLAG_TEXT["ok"] else ""] * len(row)


def _overview_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["flag"] = df["flag"].map(FLAG_TEXT)
    df["phase 0"] = df.apply(lambda r: "main" if r["main"] else ("yes" if r["d13"] else ""), axis=1)
    df["stores loaded / known"] = (
        df["stores_loaded"].astype(str) + " / " + df["stores_known"].astype(str)
    )
    out = df[
        [
            "flag",
            "name",
            "chain_id",
            "phase 0",
            "stores loaded / known",
            "items",
            "prices_today",
            "promos_today",
            "last_full_load_at",
            "last_delta_load_at",
            "hours_since_load",
        ]
    ]
    # Flagged chains first (missing, then stale), otherwise the order from the query.
    order = {FLAG_TEXT["missing"]: 0, FLAG_TEXT["stale"]: 1, FLAG_TEXT["ok"]: 2}
    return out.assign(_o=out["flag"].map(order)).sort_values("_o", kind="stable").drop(columns="_o")


def _files_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["gates"] = df["gates"].map(lambda g: ", ".join(g))
    df["gate details"] = df["gate_details"].map(lambda g: " | ".join(g))
    df = df.rename(columns={"raw_key": "raw key"})
    cols = [
        "chain_id", "kind", "published_at", "sha256", "status", "gates", "reason", "gate details",
        "raw key", "store_code",
    ]  # fmt: skip
    if df["raw key"].isna().all():
        cols.remove("raw key")  # the loader has not recorded raw file locations yet
    return df[cols]


def main() -> None:
    st.set_page_config(page_title="SmartCart ingestion", layout="wide")
    st.title("SmartCart ingestion dashboard")
    st.caption(
        "Internal. Read-only. Times are UTC. See docs/dashboard.md for what each panel means."
    )

    conn_info = resolve_dsn()
    if conn_info is None:
        st.error(
            "No database configured. Set DATABASE_URL_READONLY (the smartcart_readonly role, see "
            "docs/infra-provisioning.md) and restart."
        )
        st.stop()
    if conn_info.warning:
        st.warning(conn_info.warning)

    if st.button("Refresh"):
        st.cache_data.clear()

    sha_query = st.query_params.get("sha256", "")
    try:
        data = _load(conn_info.dsn, sha_query)
    except psycopg.Error as exc:
        st.error(f"Could not read the database: {type(exc).__name__}: {exc}")
        st.stop()

    overview = data["overview"]

    missing = [r for r in overview if r["flag"] == "missing"]
    stale = [r for r in overview if r["flag"] == "stale"]
    if missing:
        st.error(
            f"{len(missing)} of {len(PHASE0_CHAINS)} phase 0 chains have no data at all: "
            + ", ".join(r["name"] for r in missing)
        )
    if stale:
        st.error(
            f"{len(stale)} chain(s) with no successful load in the last {STALE_AFTER_HOURS} hours: "
            + ", ".join(r["name"] or r["chain_id"] for r in stale)
        )
    if not missing and not stale:
        st.success(f"Every known chain has loaded within {STALE_AFTER_HOURS} hours.")

    st.subheader("Chains")
    st.caption(
        "Coverage, freshness and counts per chain. Red rows: no load in 24 hours, or a phase 0 "
        "chain with no data at all."
    )
    frame = _overview_frame(overview)
    st.dataframe(frame.style.apply(_flag_rows, axis=1), width="stretch", hide_index=True)

    st.subheader("Failed and quarantined files")
    if data["failed"]:
        st.caption(
            "Newest first. The sha256 identifies the raw file; copy it into the lookup below."
        )
        st.dataframe(_files_frame(data["failed"]), width="stretch", hide_index=True)
    else:
        st.info("No failed or quarantined files.")

    left, right = st.columns(2)
    with left:
        st.subheader("Files per chain and status")
        if data["file_counts"]:
            counts = pd.DataFrame(data["file_counts"]).pivot_table(
                index="chain_id", columns="status", values="files", fill_value=0
            )
            st.dataframe(counts, width="stretch")
        else:
            st.info("file_tracking is empty.")
    with right:
        st.subheader("Quarantined files per chain and gate")
        if data["quarantine_counts"]:
            q = pd.DataFrame(data["quarantine_counts"]).pivot_table(
                index="chain_id", columns="gate", values="files", fill_value=0
            )
            st.dataframe(q, width="stretch")
        else:
            st.info("No quarantine events.")

    st.subheader("Look up a file by sha256")
    typed = (
        st.text_input(
            "sha256 or prefix (4+ hex characters)",
            value=sha_query,
            help="Also works as a link: add ?sha256=<hash> to the dashboard URL.",
        )
        .strip()
        .lower()
    )
    if typed != sha_query:
        st.query_params["sha256"] = typed
        st.rerun()
    if sha_query:
        matches = data["sha_matches"]
        if not matches:
            st.info("No file with that hash.")
        for m in matches:
            st.code(m["sha256"], language=None)
            st.write(
                f"{m['chain_id']} / {m['kind']} / status {m['status']}"
                + (f" / reason: {m['reason']}" if m["reason"] else "")
                + (f" / raw key: {m['raw_key']}" if m["raw_key"] else "")
            )
            for detail in m["gate_details"]:
                st.write(f"- gate {detail}")


main()
