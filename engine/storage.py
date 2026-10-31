"""Cloudflare R2 media storage (S3-compatible). Instagram fetches media from R2_PUBLIC_URL."""
import boto3

from engine.config import env


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{env('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=env("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


def upload_bytes(key: str, data: bytes, content_type: str) -> str:
    _client().put_object(Bucket=env("R2_BUCKET"), Key=key, Body=data, ContentType=content_type)
    return public_url(key)


def upload_file(key: str, path: str, content_type: str) -> str:
    with open(path, "rb") as f:
        return upload_bytes(key, f.read(), content_type)


def delete(key: str) -> None:
    _client().delete_object(Bucket=env("R2_BUCKET"), Key=key)


def public_url(key: str) -> str:
    return f"{env('R2_PUBLIC_URL').rstrip('/')}/{key}"


def download(key: str, attempts: int = 3) -> bytes:
    """Fetches an object through the storage API (not the public URL), retrying brief network errors."""
    import time
    for attempt in range(attempts):
        try:
            return _client().get_object(Bucket=env("R2_BUCKET"), Key=key)["Body"].read()
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))
