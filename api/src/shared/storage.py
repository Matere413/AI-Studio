"""R2 object-storage layer backed by boto3 (S3-compatible API).

Provides:
- ``R2Storage`` — wraps ``boto3.client("s3")`` to generate presigned URLs
  for direct client-side PUT/GET of assets stored in Cloudflare R2
  (or any S3-compatible endpoint).
- ``configure_bucket_lifecycle()`` — sets lifecycle rules that hard-purge
  objects under the ``deleted/`` prefix after ≥30 days (matching the
  soft-delete semantics of the ``Asset.deleted_at`` column).

All S3 API calls are synchronous by nature (boto3 is a sync library)
but are executed inside ``asyncio.to_thread()`` so they do not block
the async event loop in a FastAPI context.

Botocore ``ClientError`` and ``BotoCoreError`` are caught and re-raised
as ``StorageError`` so that raw S3 exception details never leak to
callers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

import boto3
import botocore
from botocore.exceptions import BotoCoreError, ClientError

_log = logging.getLogger(__name__)


class StorageError(Exception):
    """Domain exception for R2 storage-layer failures.

    Raised when a boto3 / S3 API call fails, wrapping the original
    ``ClientError`` or ``BotoCoreError`` so callers never receive raw
    S3 exception details.
    """


# Minimum number of days before a soft-deleted asset's backing object
# is hard-purged from the bucket. Must be ≥30 to match the storage spec.
_LIFECYCLE_EXPIRY_DAYS: Final[int] = 30

# Shared botocore config used for all S3 API calls — gives resilience
# against transient network failures.
_BOTOCORE_CONFIG: Final[botocore.config.Config] = botocore.config.Config(
    connect_timeout=5,
    read_timeout=10,
    retries={"max_attempts": 3},
    signature_version="s3v4",
    s3={"addressing_style": "path"},
)


class R2Storage:
    """Generate presigned URLs for direct R2 object upload/download.

    All public methods are async coroutines that delegate to the sync
    ``boto3`` client inside ``asyncio.to_thread()``, keeping the event
    loop responsive under load.

    Usage:

        storage = R2Storage(
            endpoint_url="https://<account>.r2.cloudflarestorage.com",
            access_key="<access-key-id>",
            secret_key="<secret-access-key>",
            bucket="my-bucket",
        )
        put_url = await storage.presigned_put("projects/abc/asset.webp")
        get_url = await storage.presigned_get("projects/abc/asset.webp")
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ) -> None:
        """Create an R2 storage client and validate required params.

        Args:
            endpoint_url: The S3-compatible endpoint URL (e.g. Cloudflare R2).
            access_key: R2 access key ID.
            secret_key: R2 secret access key.
            bucket: The target bucket name.
        """
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=_BOTOCORE_CONFIG,
        )

    # ── Presigned URLs ─────────────────────────────────────────────────────────

    async def presigned_put(self, key: str, ttl: int = 300, content_type: str = "image/webp") -> str:
        """Generate a presigned PUT URL for direct browser-to-R2 upload.

        Args:
            key: The object key (path) inside the bucket.
            ttl: Time-to-live in seconds (default 300 = 5 minutes).
            content_type: The MIME type of the file to be uploaded.

        Returns:
            A presigned URL string that the client can ``PUT`` to.
        """
        try:
            return await asyncio.to_thread(
                self._client.generate_presigned_url,
                ClientMethod="put_object",
                Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=ttl,
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(str(exc)) from exc

    async def presigned_get(self, key: str, ttl: int = 300) -> str:
        """Generate a presigned GET URL for secure asset download.

        Args:
            key: The object key (path) inside the bucket.
            ttl: Time-to-live in seconds (default 300 = 5 minutes).

        Returns:
            A presigned URL string.
        """
        try:
            return await asyncio.to_thread(
                self._client.generate_presigned_url,
                ClientMethod="get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=ttl,
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(str(exc)) from exc

    async def object_exists(self, key: str) -> bool:
        """Check whether an object exists in the bucket via HEAD.

        Returns ``True`` when the object is present, ``False`` when it
        returns a 404 (not found).  All other ``ClientError`` /
        ``BotoCoreError`` exceptions propagate as ``StorageError``.

        Args:
            key: The object key (path) inside the bucket.

        Returns:
            ``True`` if the object exists, ``False`` if not found.
        """
        try:
            await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._bucket,
                Key=key,
            )
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                return False
            raise StorageError(str(exc)) from exc
        except BotoCoreError as exc:
            raise StorageError(str(exc)) from exc

    async def mark_deleted(self, key: str) -> None:
        """Move an object to the ``deleted/`` prefix (copy + delete).

        First copies the object to ``deleted/{key}``, then deletes the
        original.  This ensures the object is preserved under the
        lifecycle-managed ``deleted/`` prefix until the bucket lifecycle
        rule hard-purges it (≥30 days).

        The copy happens first so that the object is never lost — if the
        copy fails, the original remains untouched.  If the copy succeeds
        but the delete fails, the object exists in both locations and
        callers may need manual cleanup.

        Args:
            key: The object key to move.

        Raises:
            StorageError: If the copy or delete operation fails.
        """
        deleted_key = f"deleted/{key}"
        try:
            await asyncio.to_thread(
                self._client.copy_object,
                Bucket=self._bucket,
                CopySource={"Bucket": self._bucket, "Key": key},
                Key=deleted_key,
            )
            await asyncio.to_thread(
                self._client.delete_object,
                Bucket=self._bucket,
                Key=key,
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(str(exc)) from exc


# ─── Bucket Lifecycle Configuration ──────────────────────────────────────────


async def configure_bucket_lifecycle(
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    expiry_days: int = _LIFECYCLE_EXPIRY_DAYS,
) -> None:
    """Apply lifecycle rules to the given bucket for soft-delete cleanup.

    Creates a lifecycle rule that hard-purges objects under the
    ``deleted/`` prefix after ``expiry_days`` (default 30, minimum spec
    requirement).  This matches the ``Asset.deleted_at`` soft-delete
    semantics: by the time the lifecycle fires, the application has already
    marked the asset as deleted, and the backend no longer serves it.

    The rule uses a ``deleted/`` prefix (not ``projects/``) so that
    active assets are NEVER caught by the expiry rule.

    This function is **idempotent** — calling it multiple times with the
    same arguments replaces the previous configuration.

    Args:
        endpoint_url: The S3-compatible endpoint URL.
        access_key: R2 access key ID.
        secret_key: R2 secret access key.
        bucket: The target bucket name.
        expiry_days: Days before objects are hard-purged (must be ≥30).

    Raises:
        ValueError: If ``expiry_days`` is less than 30.
        StorageError: If the S3 API call fails.
    """
    if expiry_days < 30:
        raise ValueError(
            f"expiry_days must be >= 30, got {expiry_days}"
        )

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=_BOTOCORE_CONFIG,
    )

    lifecycle_config = {
        "Rules": [
            {
                "ID": "purge-soft-deleted-assets",
                "Status": "Enabled",
                "Filter": {"Prefix": "deleted/"},
                "Expiration": {"Days": expiry_days},
            },
        ],
    }

    try:
        await asyncio.to_thread(
            client.put_bucket_lifecycle_configuration,
            Bucket=bucket,
            LifecycleConfiguration=lifecycle_config,
        )
    except (ClientError, BotoCoreError) as exc:
        raise StorageError(str(exc)) from exc
    _log.info(
        "bucket_lifecycle_configured",
        bucket=bucket,
        expiry_days=expiry_days,
    )
