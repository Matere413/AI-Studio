"""R2 object-storage layer backed by boto3 (S3-compatible API).

Provides:
- ``R2Storage`` — wraps ``boto3.client("s3")`` to generate presigned URLs
  for direct client-side PUT/GET of assets stored in Cloudflare R2
  (or any S3-compatible endpoint).
- ``configure_bucket_lifecycle()`` — sets lifecycle rules that hard-purge
  objects under the ``projects/`` prefix after ≥30 days (matching the
  soft-delete semantics of the ``Asset.deleted_at`` column).

All S3 API calls are synchronous by nature (boto3 is a sync library)
but are executed inside ``asyncio.to_thread()`` so they do not block
the async event loop in a FastAPI context.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

import boto3

_log = logging.getLogger(__name__)

# Minimum number of days before a soft-deleted asset's backing object
# is hard-purged from the bucket. Must be ≥30 to match the storage spec.
_LIFECYCLE_EXPIRY_DAYS: Final[int] = 30


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
        )

    # ── Presigned URLs ─────────────────────────────────────────────────────────

    async def presigned_put(self, key: str, ttl: int = 300) -> str:
        """Generate a presigned PUT URL for direct browser-to-R2 upload.

        Args:
            key: The object key (path) inside the bucket.
            ttl: Time-to-live in seconds (default 300 = 5 minutes).

        Returns:
            A presigned URL string that the client can ``PUT`` to.
        """
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            ClientMethod="put_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl,
        )

    async def presigned_get(self, key: str, ttl: int = 300) -> str:
        """Generate a presigned GET URL for secure asset download.

        Args:
            key: The object key (path) inside the bucket.
            ttl: Time-to-live in seconds (default 300 = 5 minutes).

        Returns:
            A presigned URL string.
        """
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            ClientMethod="get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl,
        )


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
    ``projects/`` prefix after ``expiry_days`` (default 30, minimum spec
    requirement).  This matches the ``Asset.deleted_at`` soft-delete
    semantics: by the time the lifecycle fires, the application has already
    marked the asset as deleted, and the backend no longer serves it.

    This function is **idempotent** — calling it multiple times with the
    same arguments replaces the previous configuration.

    Args:
        endpoint_url: The S3-compatible endpoint URL.
        access_key: R2 access key ID.
        secret_key: R2 secret access key.
        bucket: The target bucket name.
        expiry_days: Days before objects are hard-purged (must be ≥30).
    """
    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    lifecycle_config = {
        "Rules": [
            {
                "ID": "purge-soft-deleted-assets",
                "Status": "Enabled",
                "Filter": {"Prefix": "projects/"},
                "Expiration": {"Days": expiry_days},
            },
        ],
    }

    await asyncio.to_thread(
        client.put_bucket_lifecycle_configuration,
        Bucket=bucket,
        LifecycleConfiguration=lifecycle_config,
    )
    _log.info(
        "bucket_lifecycle_configured",
        bucket=bucket,
        expiry_days=expiry_days,
    )
