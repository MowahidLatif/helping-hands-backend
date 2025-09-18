import os
import uuid
import re
import boto3
from botocore.client import Config

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://127.0.0.1:9000")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "media-dev")
USE_PATH = os.getenv("S3_USE_PATH_STYLE", "true").lower() == "true"


def _client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name=S3_REGION,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=Config(s3={"addressing_style": "path" if USE_PATH else "virtual"}),
    )


_slug_re = re.compile(r"[^a-z0-9]+")


def _safe_name(name: str) -> str:
    base = name.strip().lower()
    base = _slug_re.sub("-", base).strip("-") or "file"
    return base


def make_key(org_id: str, campaign_id: str, filename: str) -> str:
    ext = ""
    if "." in filename:
        parts = filename.rsplit(".", 1)
        filename, ext = parts[0], "." + parts[1]
    return f"{org_id}/{campaign_id}/{uuid.uuid4().hex}-{_safe_name(filename)}{ext}"


def presign_put(key: str, content_type: str, expires: int = 3600) -> dict:
    s3 = _client()
    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": S3_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=expires,
        HttpMethod="PUT",
    )
    return {"upload_url": url, "required_headers": {"Content-Type": content_type}}


def public_url(key: str) -> str:
    if USE_PATH:
        return f"{S3_ENDPOINT.rstrip('/')}/{S3_BUCKET}/{key}"
    from urllib.parse import urlparse

    ep = urlparse(S3_ENDPOINT)
    return f"{ep.scheme}://{S3_BUCKET}.{ep.netloc}/{key}"
