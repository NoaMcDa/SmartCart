"""Matching commands for the ``smartcart-catalog`` CLI: embed, judge, evaluate, review.

``cli.py`` (the catalog CLI app) calls ``register(app)``. Until then, or standalone::

    uv run python -m smartcart_catalog.cli_matching evaluate --fail-below 0.98

The database is ``$DATABASE_URL``. The embedder defaults to ``$EMBEDDER`` (``hash`` when unset)
and BGE-M3's model name to ``$EMBEDDING_MODEL``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from smartcart_catalog.models import Judge


class Target(StrEnum):
    canonicals = "canonicals"
    items = "items"
    all = "all"


class JudgeName(StrEnum):
    rule = "rule"
    llm = "llm"


def _embedder(name: str | None):
    from smartcart_catalog.embed import get_embedder

    return get_embedder(name or os.environ.get("EMBEDDER") or "hash",
                        os.environ.get("EMBEDDING_MODEL"))  # fmt: skip


def _judge(name: JudgeName) -> Judge:
    from smartcart_catalog.judge import LLMJudge, RuleJudge

    if name is JudgeName.llm:
        return LLMJudge(model=os.environ.get("MATCH_JUDGE_MODEL", "claude-sonnet-5-5"))
    return RuleJudge()


def _connect():
    from smartcart_ingest import db as dbmod

    conn = dbmod.connect()
    conn.execute("SET TIME ZONE 'UTC'")
    return conn


EmbedderOpt = Annotated[
    str | None, typer.Option("--embedder", help="hash or bge-m3 (default $EMBEDDER or hash).")
]


def embed(
    target: Annotated[Target, typer.Option(help="What to embed.")] = Target.all,
    embedder: EmbedderOpt = None,
    force: Annotated[bool, typer.Option(help="Re-embed even unchanged rows.")] = False,
) -> None:
    """Embed canonicals and/or items (idempotent: unchanged rows with the same model are skipped)."""
    from smartcart_catalog.embed import embed_canonicals, embed_items

    emb = _embedder(embedder)
    with _connect() as conn:
        if target in (Target.canonicals, Target.all):
            typer.echo(json.dumps(embed_canonicals(conn, emb, force=force), ensure_ascii=False))
        if target in (Target.items, Target.all):
            typer.echo(json.dumps(embed_items(conn, emb, force=force), ensure_ascii=False))


def judge(
    judge_name: Annotated[JudgeName, typer.Option("--judge", help="rule or llm.")] = JudgeName.rule,
    k: Annotated[int, typer.Option(help="Candidates per item.")] = 10,
    item_id: Annotated[list[int] | None, typer.Option(help="Only these items.")] = None,
    dry_run: Annotated[bool, typer.Option(help="Print decisions, write nothing.")] = False,
    gold_lexicon: Annotated[
        bool,
        typer.Option(help="Use the gold set's keyword lexicon for items without extraction."),
    ] = False,
) -> None:
    """Match embedded items to canonicals and write item_canonical (never over human rows)."""
    from smartcart_catalog.block import configure_session
    from smartcart_catalog.evaluate import gold_lexicon as load_gold_lexicon
    from smartcart_catalog.match import run_matching

    lexicon = load_gold_lexicon() if gold_lexicon else None
    with _connect() as conn:
        configure_session(conn)
        results = run_matching(
            conn, _judge(judge_name), item_id or None, k=k, apply=not dry_run, lexicon=lexicon
        )
        for r in results if dry_run else []:
            typer.echo(r.decision.model_dump_json())
        accepted = sum(
            1 for r in results if r.decision.canonical_id and not r.decision.needs_review
        )
        review = sum(1 for r in results if r.decision.canonical_id and r.decision.needs_review)
        typer.echo(f"{len(results)} items: {accepted} accepted, {review} to review, "
                   f"{len(results) - accepted - review} unmapped")  # fmt: skip
        if dry_run:
            conn.rollback()


def evaluate(
    fail_below: Annotated[
        float | None,
        typer.Option(help="Exit 1 if any_brand precision is below this (e.g. 0.98)."),
    ] = None,
    embedder: EmbedderOpt = None,
    judge_name: Annotated[JudgeName, typer.Option("--judge", help="rule or llm.")] = JudgeName.rule,
    k: Annotated[int, typer.Option(help="Candidates per item (recall@k).")] = 10,
    gold_dir: Annotated[Path | None, typer.Option(help="Gold set directory.")] = None,
    no_load: Annotated[bool, typer.Option("--no-load", help="Use gold_pairs as loaded.")] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Print the metrics as JSON.")] = False,
) -> None:
    """Precision and recall per flexibility level on the gold set; saved to match_runs."""
    from smartcart_catalog.evaluate import (
        DEFAULT_GOLD_DIR,
        format_report,
        passes,
        run_evaluation,
    )

    with _connect() as conn:
        report = run_evaluation(conn, _judge(judge_name), _embedder(embedder), k=k,
                                gold_dir=gold_dir or DEFAULT_GOLD_DIR, load=not no_load)  # fmt: skip
        conn.commit()
    if json_out:
        typer.echo(json.dumps({**report.metrics.model_dump(mode="json"), **report.extra},
                              ensure_ascii=False, indent=2))  # fmt: skip
    else:
        typer.echo(format_report(report))
    if fail_below is not None and not passes(report.metrics, fail_below):
        got = report.metrics.precision.get("any_brand")
        typer.echo(f"FAIL: any_brand precision {got if got is not None else 'n/a'} < {fail_below}",
                   err=True)  # fmt: skip
        raise typer.Exit(1)


def review(
    port: Annotated[int, typer.Option(help="Streamlit port.")] = 8502,
) -> None:
    """Open the Streamlit review UI (needs the `review` extra)."""
    if importlib.util.find_spec("streamlit") is None:
        typer.echo(
            "The review UI needs Streamlit, which is the optional 'review' extra of "
            "smartcart-catalog.\nInstall it with:  uv sync --extra review --package "
            "smartcart-catalog   (or: uv sync --all-packages)",
            err=True,
        )
        raise typer.Exit(2)
    app_path = Path(__file__).with_name("review_app.py")
    raise typer.Exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app_path),
                                      "--server.port", str(port)]))  # fmt: skip


def register(app: typer.Typer) -> None:
    """Add the matching commands to the catalog CLI."""
    app.command("embed")(embed)
    app.command("judge")(judge)
    app.command("evaluate")(evaluate)
    app.command("review")(review)


app = typer.Typer(help="SmartCart matching: embeddings, judge, evaluation, review UI.",
                  no_args_is_help=True)  # fmt: skip
register(app)

if __name__ == "__main__":
    app()
