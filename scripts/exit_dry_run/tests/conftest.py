"""Reuse the ingest suite's throwaway Postgres (``pg_dsn``), as services/catalog/tests does."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[3] / "services" / "ingest" / "tests" / "conftest.py"
_spec = importlib.util.spec_from_file_location("_ingest_test_fixtures_dry_run", _PATH)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module  # dataclasses looks the module up by name
_spec.loader.exec_module(_module)

pg_dsn = _module.pg_dsn
