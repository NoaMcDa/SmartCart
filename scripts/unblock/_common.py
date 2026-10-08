"""Small helpers shared by the scripts in ``scripts/unblock`` (standard library only).

The scripts run as ``uv run --no-sync python scripts/unblock/<name>.py`` from the repo root, so
this directory is ``sys.path[0]`` and ``import _common`` works without a package.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def venv_bin(name: str) -> str:
    """The console script ``name`` next to the running interpreter (the project's .venv), so a
    subprocess never re-syncs the environment the way ``uv run`` would."""
    candidate = Path(sys.executable).parent / name
    return str(candidate) if candidate.exists() else name


@dataclass
class Completed:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    seconds: float


def run(args: list[str], *, env: dict[str, str] | None = None, check: bool = True) -> Completed:
    """Run a command, echo it, capture its output and time it. ``check`` raises on non-zero."""
    print("+ " + " ".join(args), file=sys.stderr, flush=True)
    start = time.monotonic()
    res = subprocess.run(
        args, capture_output=True, text=True, env={**os.environ, **(env or {})}, cwd=REPO
    )
    took = time.monotonic() - start
    if res.stderr:
        sys.stderr.write(res.stderr[-4000:])
    if check and res.returncode != 0:
        sys.stderr.write(res.stdout[-4000:])
        raise SystemExit(f"command failed ({res.returncode}): {' '.join(args)}")
    return Completed(args, res.returncode, res.stdout, res.stderr, took)


def last_json_document(text: str) -> dict:
    """The JSON object printed last on stdout, ignoring any log lines before it."""
    lines = text.splitlines()
    for start in range(len(lines)):
        if lines[start].startswith("{"):
            try:
                return json.loads("\n".join(lines[start:]))
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON object found in the command output")


def json_lines(text: str) -> list[dict]:
    """Every line of ``text`` that is a JSON object."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def fmt(value: float | None, digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def md_escape(text: object) -> str:
    """Make a value safe for one Markdown table cell (pipes and newlines)."""
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def git_sha() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha[:12]
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True, cwd=REPO
        )
    except OSError:
        return "unknown"
    return res.stdout.strip() or "unknown"


def write_text(path: Path | None, text: str) -> None:
    if path is None:
        sys.stdout.write(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path}", file=sys.stderr)
