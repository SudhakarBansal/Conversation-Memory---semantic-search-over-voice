"""Nyas S3-compatible storage via boto3: upload clips + make presigned URLs."""
from functools import lru_cache

import boto3
from botocore.config import Config
from app.config import (
    S3_ENDPOINT, S3_REGION, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET,
)

# Nyas uses path-style addressing (bucket in the path, not the hostname).
_s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION,
    config=Config(s3={"addressing_style": "path"}),
)


def upload_file(local_path: str, key: str, content_type: str = "audio/flac"):
    """Upload one local file to the bucket under `key`."""
    with open(local_path, "rb") as f:
        _s3.put_object(Bucket=S3_BUCKET, Key=key, Body=f, ContentType=content_type)


def list_keys() -> set[str]:
    """Return the set of object keys already in the bucket (for skip-on-reingest)."""
    keys = set()
    token = None
    while True:
        kw = {"Bucket": S3_BUCKET}
        if token:
            kw["ContinuationToken"] = token
        resp = _s3.list_objects_v2(**kw)
        keys.update(o["Key"] for o in resp.get("Contents", []))
        if not resp.get("IsTruncated"):
            break
        token = resp["NextContinuationToken"]
    return keys


def delete_object(key: str):
    """Delete one object (best-effort; ignores 'already gone')."""
    _s3.delete_object(Bucket=S3_BUCKET, Key=key)


@lru_cache(maxsize=4)
def get_bytes(key: str) -> bytes:
    """Fetch a whole object's bytes (cached). Nyas storage doesn't honor HTTP
    Range requests, so the browser can't seek a presigned URL — we serve the
    audio ourselves with Range support and slice from these bytes."""
    return _s3.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read()


def presigned_url(key: str, expires: int = 3600) -> str:
    """A temporary public URL the browser can use to play a clip."""
    return _s3.generate_presigned_url(
        "get_object", Params={"Bucket": S3_BUCKET, "Key": key}, ExpiresIn=expires
    )
