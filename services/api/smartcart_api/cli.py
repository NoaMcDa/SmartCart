"""``smartcart-api`` command line.

    smartcart-api serve [--host 0.0.0.0] [--port 8000] [--reload]
    smartcart-api precompute [--as-of 2026-10-07T03:00:00+03:00] [--chain ID ...]

``precompute`` is the nightly job of issue #47: run it after the daily ingestion load. It reads
``DATABASE_URL``, commits once at the end and prints the run's metrics as JSON.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated

import psycopg
import typer

from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.settings import get_settings

app = typer.Typer(help="SmartCart API: serve the API and run its batch jobs.", no_args_is_help=True)


def _connect() -> psycopg.Connection:
    url = get_settings().database_url
    if not url:
        raise typer.BadParameter("DATABASE_URL is not set")
    return psycopg.connect(url)


@app.command()
def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """Run the API with uvicorn."""
    import uvicorn

    uvicorn.run("smartcart_api.main:app", host=host, port=port, reload=reload)


@app.command()
def precompute(
    as_of: Annotated[
        datetime | None, typer.Option(help="Price and promo time (default: now)")
    ] = None,
    chain: Annotated[
        list[str] | None, typer.Option(help="Only these chains (repeatable); default: all")
    ] = None,
) -> None:
    """Recompute effective_prices (best item per canonical, store and flex level)."""
    with _connect() as conn:  # the connection's context commits on success
        result = precompute_effective_prices(conn, as_of=as_of, chains=chain or None)
    typer.echo(json.dumps({"run_id": result.run_id, **result.metrics()}, ensure_ascii=False))


if __name__ == "__main__":
    app()
