"""Raw archive of every downloaded transparency file (issue #37, CLAUDE.md "Storage").

Keys look like ``raw/<chain_id>/<yyyy>/<mm>/<dd>/<original filename>``; the date is the file's
publication day in Israel time. If two different contents arrive under the same filename on the
same day (a chain republishing), the second one goes to
``raw/<chain_id>/<yyyy>/<mm>/<dd>/dup-<sha256[:12]>/<filename>`` so neither overwrites the other.

``LocalRawStore`` writes under a directory (``RAW_STORE_PATH``). ``S3RawStore`` is a thin boto3
wrapper for Cloudflare R2 or AWS S3 (``S3_*`` variables from ``.env.example``).
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from smartcart_ingest.settings import Settings

ISRAEL = ZoneInfo("Asia/Jerusalem")


class RawStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


class RawStoreKeyError(ValueError):
    """A key that would escape the archive root or is otherwise malformed."""


def _check_key(key: str) -> str:
    path = PurePosixPath(key)
    if not key or path.is_absolute() or ".." in path.parts or "\\" in key:
        raise RawStoreKeyError(f"bad raw store key: {key!r}")
    return key


def raw_key(chain_id: str, published_at: datetime, filename: str) -> str:
    """``raw/<chain_id>/<yyyy>/<mm>/<dd>/<filename>``, the date in Israel time."""
    name = PurePosixPath(filename).name
    if not name or name in {".", ".."}:
        raise RawStoreKeyError(f"bad filename: {filename!r}")
    local = published_at.astimezone(ISRAEL) if published_at.tzinfo else published_at
    return f"raw/{chain_id}/{local:%Y}/{local:%m}/{local:%d}/{name}"


def duplicate_key(key: str, sha256: str) -> str:
    """Where a different content with the same filename and day is archived."""
    path = PurePosixPath(key)
    return str(path.parent / f"dup-{sha256[:12]}" / path.name)


class LocalRawStore:
    """Files under ``root``. Writes are atomic (temp file plus rename)."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / _check_key(key)

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


class S3RawStore:
    """Objects in an S3-compatible bucket. ``client`` is a boto3 S3 client (or a stand-in)."""

    def __init__(self, bucket: str, client: Any) -> None:
        self.bucket = bucket
        self.client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> S3RawStore:
        import boto3  # imported here so the local store needs no AWS SDK at import time

        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET is not set")
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )
        return cls(settings.s3_bucket, client)

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=_check_key(key), Body=data)

    def get(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=_check_key(key))
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=_check_key(key))
        except Exception as exc:  # botocore.exceptions.ClientError, without importing botocore
            response = getattr(exc, "response", None) or {}
            code = str(response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True


def rawstore_from_settings(settings: Settings) -> RawStore:
    """S3 when ``S3_BUCKET`` is set, else a local directory from ``RAW_STORE_PATH``."""
    if settings.s3_bucket:
        return S3RawStore.from_settings(settings)
    if settings.raw_store_path:
        return LocalRawStore(settings.raw_store_path)
    raise ValueError("no raw store configured: set S3_BUCKET (and S3_*) or RAW_STORE_PATH")
