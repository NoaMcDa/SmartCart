"""Write the OpenAPI document the web app generates its types from.

Usage: uv run python -m smartcart_api.export_openapi [path]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from smartcart_api.main import app

DEFAULT = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "api" / "openapi.json"


def export(path: Path = DEFAULT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    print(export(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT))
