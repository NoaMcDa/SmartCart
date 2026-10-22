"""Reuse the ingest suite's throwaway Postgres (``pg_dsn``), as scripts/exit_dry_run does."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[3] / "services" / "ingest" / "tests" / "conftest.py"
_spec = importlib.util.spec_from_file_location("_ingest_test_fixtures_exit_window", _PATH)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module  # dataclasses looks the module up by name
_spec.loader.exec_module(_module)

pg_dsn = _module.pg_dsn
