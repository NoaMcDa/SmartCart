#!/usr/bin/env python3
"""Upload, read back and delete one small object in the raw-archive bucket.

Works with Cloudflare R2 and AWS S3 (anything boto3 can talk to over the S3 API).

Third-party dependency: boto3 only. Run it without installing anything into the project:

    uv run infra/smoke/bucket_roundtrip.py

(the inline metadata below tells uv to fetch boto3 for this script alone).

Environment variables (see .env.example, no defaults for secrets):
    S3_BUCKET             bucket name (required)
    S3_ACCESS_KEY_ID      access key of the least-privilege credential (required)
    S3_SECRET_ACCESS_KEY  its secret (required)
    S3_ENDPOINT_URL       R2: https://<account id>.r2.cloudflarestorage.com ; leave unset for S3
    S3_REGION             R2: auto (default) ; S3: the bucket's region, for example eu-central-1
    S3_KEY_PREFIX         key prefix for the test object (default "smoke/")
    SMOKE_REQUIRE_DELETE  1 to fail when the credential cannot delete (default 0)

Exit codes: 0 round trip passed; 1 failed; 2 configuration missing.

An ingest credential for a write-once archive should not be able to delete. In that case the
upload and the read-back still prove access, the delete is reported as a warning, and the test
object is left under the smoke prefix for an admin to remove (or for a lifecycle rule to expire).
"""

# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3>=1.34"]
# ///

from __future__ import annotations

import hashlib
import os
import sys
import uuid
from datetime import UTC, datetime

REQUIRED = ("S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")


def main() -> int:
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        print(f"missing environment variables: {', '.join(missing)}", file=sys.stderr)
        return 2

    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        print("boto3 is not installed. Run: uv run infra/smoke/bucket_roundtrip.py", file=sys.stderr)
        return 2

    bucket = os.environ["S3_BUCKET"]
    endpoint = os.environ.get("S3_ENDPOINT_URL") or None
    region = os.environ.get("S3_REGION") or ("auto" if endpoint else None)
    prefix = os.environ.get("S3_KEY_PREFIX") or "smoke/"
    require_delete = os.environ.get("SMOKE_REQUIRE_DELETE") == "1"

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    key = f"{prefix}{stamp}-{uuid.uuid4().hex[:8]}.txt"
    body = f"smartcart bucket smoke test {stamp}\n".encode()
    digest = hashlib.sha256(body).hexdigest()
    print(f"bucket={bucket} endpoint={endpoint or 'aws default'} key={key}")

    try:
        client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="text/plain")
        print("upload:   ok")

        got = client.get_object(Bucket=bucket, Key=key)["Body"].read()
        if hashlib.sha256(got).hexdigest() != digest:
            print("read-back: FAIL, content differs from what was uploaded", file=sys.stderr)
            return 1
        print("read-back: ok (sha256 matches)")
    except (ClientError, BotoCoreError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    try:
        client.delete_object(Bucket=bucket, Key=key)
        print("delete:   ok")
    except (ClientError, BotoCoreError) as exc:
        if require_delete:
            print(f"delete: FAIL ({exc})", file=sys.stderr)
            return 1
        print(f"delete:   denied or failed ({exc}).")
        print(f"WARN: remove s3://{bucket}/{key} with an admin credential.")

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
