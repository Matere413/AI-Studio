"""Unit tests for the R2Storage presigned URL generation layer.

Covers presigned PUT/GET URL generation via mocked ``boto3.client("s3")``,
lifecycle configuration, and async wrapper behavior.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.shared.storage import R2Storage, configure_bucket_lifecycle


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_s3_client():
    """Return a MagicMock that stands in for ``boto3.client("s3")``.

    The mock's ``generate_presigned_url`` returns a predictable URL
    so tests can verify URL generation without real AWS credentials.
    """
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://r2.example.com/presigned-url"
    return client


@pytest.fixture
def storage(mock_s3_client):
    """Return an ``R2Storage`` instance backed by a mocked S3 client.

    All ``boto3.client`` calls inside ``R2Storage.__init__`` are
    replaced by ``mock_s3_client`` so tests never reach a real S3/R2
    endpoint.
    """
    with patch("src.shared.storage.boto3.client", return_value=mock_s3_client):
        yield R2Storage(
            endpoint_url="https://r2.example.com",
            access_key="test-access-key",
            secret_key="test-secret-key",
            bucket="test-bucket",
        )


@pytest.fixture
def error_client():
    """Return an S3 client mock that raises on presigned URL generation.

    Used to verify that ``R2Storage`` propagates boto3 exceptions
    rather than silently swallowing them.
    """
    client = MagicMock()
    client.generate_presigned_url.side_effect = Exception("boto3 error")
    return client


# ─── R2Storage: Constructor ─────────────────────────────────────────────────


class TestR2StorageConstructor:
    """R2Storage MUST initialise the boto3 S3 client with R2-compatible config."""

    async def test_constructor_creates_s3_client_with_r2_endpoint(self):
        """GIVEN R2Storage is instantiated
        WHEN boto3.client is patched
        THEN boto3.client("s3") is called with the correct endpoint_url.
        """
        with patch("src.shared.storage.boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()
            R2Storage(
                endpoint_url="https://r2.custom.com",
                access_key="ak",
                secret_key="sk",
                bucket="b",
            )

        mock_boto3_client.assert_called_once_with(
            "s3",
            endpoint_url="https://r2.custom.com",
            aws_access_key_id="ak",
            aws_secret_access_key="sk",
        )


# ─── R2Storage: presigned_put ────────────────────────────────────────────────


class TestPresignedPut:
    """presigned_put() MUST generate a presigned PUT URL via boto3."""

    async def test_presigned_put_calls_generate_presigned_url(self, storage, mock_s3_client):
        """GIVEN an R2Storage instance with a mocked S3 client
        WHEN presigned_put("photos/portrait.webp", ttl=300) is called
        THEN boto3 generate_presigned_url is called with ClientMethod="put_object"
        and the correct Params, and the returned URL is returned as a string.
        """
        url = await storage.presigned_put("photos/portrait.webp", ttl=300)

        mock_s3_client.generate_presigned_url.assert_called_once_with(
            ClientMethod="put_object",
            Params={"Bucket": "test-bucket", "Key": "photos/portrait.webp"},
            ExpiresIn=300,
        )
        assert url == "https://r2.example.com/presigned-url"

    async def test_presigned_put_custom_ttl(self, storage, mock_s3_client):
        """GIVEN a custom TTL of 600 seconds
        WHEN presigned_put is called with ttl=600
        THEN ExpiresIn=600 is passed to generate_presigned_url.
        """
        await storage.presigned_put("photos/custom-ttl.webp", ttl=600)

        call_kwargs = mock_s3_client.generate_presigned_url.call_args.kwargs
        assert call_kwargs["ExpiresIn"] == 600

    async def test_presigned_put_default_ttl_is_300(self, storage, mock_s3_client):
        """GIVEN no custom TTL is provided
        WHEN presigned_put is called without ttl
        THEN ExpiresIn=300 is passed (default).
        """
        await storage.presigned_put("photos/default-ttl.webp")

        call_kwargs = mock_s3_client.generate_presigned_url.call_args.kwargs
        assert call_kwargs["ExpiresIn"] == 300


# ─── R2Storage: presigned_get ────────────────────────────────────────────────


class TestPresignedGet:
    """presigned_get() MUST generate a presigned GET URL via boto3."""

    async def test_presigned_get_calls_generate_presigned_url(self, storage, mock_s3_client):
        """GIVEN an R2Storage instance with a mocked S3 client
        WHEN presigned_get("photos/portrait.webp", ttl=300) is called
        THEN boto3 generate_presigned_url is called with ClientMethod="get_object"
        and the correct Params, and the returned URL is returned as a string.
        """
        url = await storage.presigned_get("photos/portrait.webp", ttl=300)

        mock_s3_client.generate_presigned_url.assert_called_once_with(
            ClientMethod="get_object",
            Params={"Bucket": "test-bucket", "Key": "photos/portrait.webp"},
            ExpiresIn=300,
        )
        assert url == "https://r2.example.com/presigned-url"

    async def test_presigned_get_custom_ttl(self, storage, mock_s3_client):
        """GIVEN a custom TTL of 120 seconds
        WHEN presigned_get is called with ttl=120
        THEN ExpiresIn=120 is passed to generate_presigned_url.
        """
        await storage.presigned_get("photos/custom.webp", ttl=120)

        call_kwargs = mock_s3_client.generate_presigned_url.call_args.kwargs
        assert call_kwargs["ExpiresIn"] == 120


# ─── R2Storage: Error handling ──────────────────────────────────────────────


class TestR2StorageErrors:
    """R2Storage MUST propagate boto3 exceptions to callers."""

    async def test_presigned_put_propagates_boto3_error(self, storage, error_client, mock_s3_client):
        """GIVEN the S3 client raises on generate_presigned_url
        WHEN presigned_put is called
        THEN the exception is propagated (not swallowed).
        """
        mock_s3_client.generate_presigned_url.side_effect = Exception("boto3 error")
        with pytest.raises(Exception, match="boto3 error"):
            await storage.presigned_put("photos/fail.webp")

    async def test_presigned_get_propagates_boto3_error(self, storage, error_client, mock_s3_client):
        """GIVEN the S3 client raises on generate_presigned_url
        WHEN presigned_get is called
        THEN the exception is propagated (not swallowed).
        """
        mock_s3_client.generate_presigned_url.side_effect = Exception("boto3 error")
        with pytest.raises(Exception, match="boto3 error"):
            await storage.presigned_get("photos/fail.webp")


# ─── Task 2.3: Bucket lifecycle configuration ────────────────────────────────


class TestConfigureBucketLifecycle:
    """configure_bucket_lifecycle() MUST set R2 bucket lifecycle rules."""

    async def test_configure_lifecycle_calls_put_bucket_lifecycle(self):
        """GIVEN a mocked S3 client
        WHEN configure_bucket_lifecycle() is called
        THEN put_bucket_lifecycle_configuration is invoked with the correct
        lifecycle rule for soft-deleted assets (prefix "projects/", ≥30 day expiry).
        """
        mock_client = MagicMock()
        with patch("src.shared.storage.boto3.client", return_value=mock_client):
            await configure_bucket_lifecycle(
                endpoint_url="https://r2.example.com",
                access_key="ak",
                secret_key="sk",
                bucket="test-bucket",
            )

        mock_client.put_bucket_lifecycle_configuration.assert_called_once()
        call_args = mock_client.put_bucket_lifecycle_configuration.call_args

        # Verify bucket name
        assert call_args.kwargs["Bucket"] == "test-bucket"

        # Verify lifecycle rule structure
        rules = call_args.kwargs["LifecycleConfiguration"]["Rules"]
        assert len(rules) >= 1

        # The soft-delete rule: prefix "projects/", expiration after ≥30 days
        soft_delete_rule = next(r for r in rules if r["Status"] == "Enabled")
        assert soft_delete_rule["Expiration"]["Days"] >= 30
        assert soft_delete_rule["Filter"]["Prefix"] == "projects/"

    async def test_configure_lifecycle_calls_with_custom_bucket(self):
        """GIVEN configure_bucket_lifecycle is called with a custom bucket name
        WHEN invoked
        THEN the lifecycle config is applied to that exact bucket.
        """
        mock_client = MagicMock()
        with patch("src.shared.storage.boto3.client", return_value=mock_client):
            await configure_bucket_lifecycle(
                endpoint_url="https://r2.example.com",
                access_key="ak",
                secret_key="sk",
                bucket="custom-bucket",
            )

        call_kwargs = mock_client.put_bucket_lifecycle_configuration.call_args.kwargs
        assert call_kwargs["Bucket"] == "custom-bucket"
