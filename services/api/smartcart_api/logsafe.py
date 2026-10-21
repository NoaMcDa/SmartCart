"""Log configuration that keeps personal data out of the access log (docs/security-review.md).

Uvicorn's access log prints the request line, query string included. ``GET /stores/nearest`` and
``GET /items/barcode/{code}`` carry the caller's coordinates (``lat``, ``lon``) in the query, so
the default log would record where a person was standing, at full precision, which is the thing
the app promises to store only at neighborhood level (D11). ``StripQuery`` cuts the query string
off the logged request line: the access log keeps method, path, status and the peer address,
nothing the caller typed. (Request bodies, ``Authorization`` headers and uploaded images are never
logged by uvicorn or by this code.)

``uvicorn_log_config()`` is the stock uvicorn config plus that filter; ``smartcart-api serve`` and
``smartcart_api.main.run`` pass it as ``log_config``.
"""

from __future__ import annotations

import copy
import logging
from typing import Any


class StripQuery(logging.Filter):
    """Drop ``?query`` from the request line of a ``uvicorn.access`` record."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        # uvicorn: "%s - \"%s %s HTTP/%s\" %d" % (client, method, full_path, version, status)
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            path = args[2].split("?", 1)[0]
            record.args = (*args[:2], path, *args[3:])
        return True


def uvicorn_log_config() -> dict[str, Any]:
    from uvicorn.config import LOGGING_CONFIG

    config = copy.deepcopy(LOGGING_CONFIG)
    config.setdefault("filters", {})["strip_query"] = {"()": f"{__name__}.StripQuery"}
    config["loggers"]["uvicorn.access"]["filters"] = ["strip_query"]
    return config
