"""Bridge to the pinned upstream scraper for ``download.ScraperFetcher``.

The adapter contract keeps every ``il_supermarket_scarper`` import inside this package, so the
fetcher in ``smartcart_ingest.download`` gets the upstream entry points from here. Call
``smartcart_ingest.download.quiet_upstream_loggers()`` first (``download.load_upstream`` does):
upstream opens ``logging.log`` in the working directory at import time otherwise.
"""

from __future__ import annotations

from typing import Any


def scraper_api() -> tuple[Any, Any]:
    """``(ScraperFactory, DiskFileOutput)`` from il_supermarket_scarper."""
    from il_supermarket_scarper import ScraperFactory
    from il_supermarket_scarper.utils.files.file_output import DiskFileOutput

    return ScraperFactory, DiskFileOutput
