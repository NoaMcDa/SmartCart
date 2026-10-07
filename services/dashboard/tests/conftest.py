"""Reuse the ingest suite's database fixtures (``db``, ``database``, ``pg_dsn``).

They live in services/ingest/tests/conftest.py (DATABASE_URL, or a throwaway Postgres cluster
migrated with the repo's migrations). That file is loaded by path and its fixtures are
re-exported here, so the dashboard tests get the same database without importing across test
packages. This directory has no ``__init__.py`` on purpose: services/ingest/tests is already the
top-level package ``tests``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "ingest" / "tests" / "conftest.py"
_spec = importlib.util.spec_from_file_location("_ingest_test_fixtures", _PATH)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module  # dataclasses looks the module up by name
_spec.loader.exec_module(_module)

pg_dsn = _module.pg_dsn
database = _module.database
db = _module.db
_skip_without_extension = _module._skip_without_extension
