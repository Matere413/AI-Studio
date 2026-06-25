"""Unit tests for the R2Storage presigned URL generation layer.

Covers presigned PUT/GET URL generation via mocked ``boto3.client("s3")``,
lifecycle configuration, async wrapper behavior, timeout/resilience config,
botocore error → StorageError translation, and expiry validation.
"""

from unittest.mock import ANY, MagicMock, patch

import botocore
import pytest
from botocore.exceptions import BotoCoreError, ClientError

from src.shared.storage import R2Storage, StorageError, configure_bucket_lifecycle


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


# ─── R2Storage: Constructor ─────────────────────────────────────────────────


class TestR2StorageConstructor:
    """R2Storage MUST initialise the boto3 S3 client with R2-compatible config."""

    async def test_constructor_creates_s3_client_with_r2_endpoint(self):
        """GIVEN R2Storage is instantiated
        WHEN boto3.client is patched
        THEN boto3.client("s3") is called with the correct endpoint_url
        and a botocore config.
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
            config=ANY,
        )

    async def test_constructor_creates_s3_client_with_botocore_config(self):
        """GIVEN R2Storage is instantiated
        THEN boto3.client receives a botocore.config.Config with
        connect_timeout=5, read_timeout=10, retries={'max_attempts': 3}.
        """
        with patch("src.shared.storage.boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()
            R2Storage(
                endpoint_url="https://r2.example.com",
                access_key="ak",
                secret_key="sk",
                bucket="b",
            )

        config = mock_boto3_client.call_args.kwargs["config"]
        assert isinstance(config, botocore.config.Config)
        assert config.connect_timeout == 5
        assert config.read_timeout == 10
        assert config.retries == {"max_attempts": 3}


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
    """R2Storage MUST raise StorageError on botocore failures."""

    async def test_presigned_put_raises_storage_error_on_client_error(self, storage, mock_s3_client):
        """GIVEN the S3 client raises ClientError on generate_presigned_url
        WHEN presigned_put is called
        THEN StorageError is raised.
        """
        mock_s3_client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "boto3 error"}},
            "generate_presigned_url",
        )
        with pytest.raises(StorageError, match="boto3 error"):
            await storage.presigned_put("photos/fail.webp")

    async def test_presigned_get_raises_storage_error_on_client_error(self, storage, mock_s3_client):
        """GIVEN the S3 client raises ClientError on generate_presigned_url
        WHEN presigned_get is called
        THEN StorageError is raised.
        """
        mock_s3_client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "boto3 error"}},
            "generate_presigned_url",
        )
        with pytest.raises(StorageError, match="boto3 error"):
            await storage.presigned_get("photos/fail.webp")

    async def test_presigned_put_raises_storage_error_on_botocore_error(self, storage, mock_s3_client):
        """GIVEN the S3 client raises a generic BotoCoreError
        WHEN presigned_put is called
        THEN StorageError is raised.
        """
        mock_s3_client.generate_presigned_url.side_effect = BotoCoreError()
        with pytest.raises(StorageError):
            await storage.presigned_put("photos/fail.webp")

    async def test_presigned_get_raises_storage_error_on_botocore_error(self, storage, mock_s3_client):
        """GIVEN the S3 client raises a generic BotoCoreError
        WHEN presigned_get is called
        THEN StorageError is raised.
        """
        mock_s3_client.generate_presigned_url.side_effect = BotoCoreError()
        with pytest.raises(StorageError):
            await storage.presigned_get("photos/fail.webp")


# ─── R2Storage: mark_deleted (copy + delete) ────────────────────────────────


class TestMarkDeleted:
    """mark_deleted() MUST copy to deleted/ prefix then delete original."""

    async def test_mark_deleted_copies_then_deletes(self, storage, mock_s3_client):
        """GIVEN an R2Storage instance
        WHEN mark_deleted("projects/abc/asset.webp") is called
        THEN copy_object is called with CopySource + Key="deleted/projects/abc/asset.webp"
        AND THEN delete_object is called with the original key.
        """
        await storage.mark_deleted("projects/abc/asset.webp")

        mock_s3_client.copy_object.assert_called_once_with(
            Bucket="test-bucket",
            CopySource={"Bucket": "test-bucket", "Key": "projects/abc/asset.webp"},
            Key="deleted/projects/abc/asset.webp",
        )
        mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="projects/abc/asset.webp",
        )

    async def test_mark_deleted_prefixed_already_deleted(self, storage, mock_s3_client):
        """GIVEN a key that is already under the deleted/ prefix
        WHEN mark_deleted is called
        THEN the object is copied to deleted/deleted/{key} (idempotent double-wrap).
        """
        await storage.mark_deleted("deleted/old/asset.webp")

        mock_s3_client.copy_object.assert_called_once_with(
            Bucket="test-bucket",
            CopySource={"Bucket": "test-bucket", "Key": "deleted/old/asset.webp"},
            Key="deleted/deleted/old/asset.webp",
        )

    async def test_mark_deleted_raises_storage_error_on_copy_failure(self, storage, mock_s3_client):
        """GIVEN copy_object raises ClientError
        WHEN mark_deleted is called
        THEN StorageError is raised and delete_object is NOT called.
        """
        mock_s3_client.copy_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "copy failed"}},
            "copy_object",
        )

        with pytest.raises(StorageError, match="copy failed"):
            await storage.mark_deleted("projects/abc/asset.webp")

        mock_s3_client.delete_object.assert_not_called()

    async def test_mark_deleted_raises_storage_error_on_delete_failure(self, storage, mock_s3_client):
        """GIVEN copy_object succeeds but delete_object raises ClientError
        WHEN mark_deleted is called
        THEN StorageError is raised (copy still happened, original not removed).
        """
        mock_s3_client.copy_object.return_value = {"CopyObjectResult": {"ETag": "abc"}}
        mock_s3_client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "delete failed"}},
            "delete_object",
        )

        with pytest.raises(StorageError, match="delete failed"):
            await storage.mark_deleted("projects/abc/asset.webp")

        # copy_object was still called
        mock_s3_client.copy_object.assert_called_once()

    async def test_mark_deleted_raises_on_botocore_error(self, storage, mock_s3_client):
        """GIVEN copy_object raises BotoCoreError
        WHEN mark_deleted is called
        THEN StorageError is raised.
        """
        mock_s3_client.copy_object.side_effect = BotoCoreError()

        with pytest.raises(StorageError):
            await storage.mark_deleted("projects/abc/asset.webp")


# ─── Task 2.3: Bucket lifecycle configuration ────────────────────────────────


class TestConfigureBucketLifecycle:
    """configure_bucket_lifecycle() MUST set R2 bucket lifecycle rules."""

    async def test_configure_lifecycle_calls_put_bucket_lifecycle(self):
        """GIVEN a mocked S3 client
        WHEN configure_bucket_lifecycle() is called
        THEN put_bucket_lifecycle_configuration is invoked with the correct
        lifecycle rule for soft-deleted assets (prefix "deleted/", ≥30 day expiry).
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

        # The soft-delete rule: prefix "deleted/", expiration after ≥30 days
        soft_delete_rule = next(r for r in rules if r["Status"] == "Enabled")
        assert soft_delete_rule["Expiration"]["Days"] >= 30
        assert soft_delete_rule["Filter"]["Prefix"] == "deleted/"

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

    async def test_lifecycle_rejects_expiry_below_30(self):
        """GIVEN expiry_days=29
        WHEN configure_bucket_lifecycle is called
        THEN ValueError is raised.
        """
        with pytest.raises(ValueError, match="expiry_days"):
            await configure_bucket_lifecycle(
                endpoint_url="https://r2.example.com",
                access_key="ak",
                secret_key="sk",
                bucket="test-bucket",
                expiry_days=29,
            )

    async def test_lifecycle_accepts_expiry_at_30(self):
        """GIVEN expiry_days=30 (minimum allowed)
        WHEN configure_bucket_lifecycle is called
        THEN it succeeds with the minimum allowed expiry.
        """
        mock_client = MagicMock()
        with patch("src.shared.storage.boto3.client", return_value=mock_client):
            await configure_bucket_lifecycle(
                endpoint_url="https://r2.example.com",
                access_key="ak",
                secret_key="sk",
                bucket="test-bucket",
                expiry_days=30,
            )

        mock_client.put_bucket_lifecycle_configuration.assert_called_once()
        rules = mock_client.put_bucket_lifecycle_configuration.call_args.kwargs["LifecycleConfiguration"]["Rules"]
        assert rules[0]["Expiration"]["Days"] == 30

    async def test_lifecycle_accepts_expiry_above_30(self):
        """GIVEN expiry_days=60 (greater than minimum)
        WHEN configure_bucket_lifecycle is called
        THEN it succeeds with the custom expiry.
        """
        mock_client = MagicMock()
        with patch("src.shared.storage.boto3.client", return_value=mock_client):
            await configure_bucket_lifecycle(
                endpoint_url="https://r2.example.com",
                access_key="ak",
                secret_key="sk",
                bucket="test-bucket",
                expiry_days=60,
            )

        mock_client.put_bucket_lifecycle_configuration.assert_called_once()
        rules = mock_client.put_bucket_lifecycle_configuration.call_args.kwargs["LifecycleConfiguration"]["Rules"]
        assert rules[0]["Expiration"]["Days"] == 60

    async def test_lifecycle_prefix_is_deleted(self):
        """GIVEN configure_bucket_lifecycle is called
        THEN the lifecycle filter prefix is "deleted/", not "projects/".
        """
        mock_client = MagicMock()
        with patch("src.shared.storage.boto3.client", return_value=mock_client):
            await configure_bucket_lifecycle(
                endpoint_url="https://r2.example.com",
                access_key="ak",
                secret_key="sk",
                bucket="test-bucket",
            )

        rules = mock_client.put_bucket_lifecycle_configuration.call_args.kwargs["LifecycleConfiguration"]["Rules"]
        assert rules[0]["Filter"]["Prefix"] == "deleted/"

    async def test_lifecycle_raises_storage_error_on_client_error(self):
        """GIVEN the S3 client raises ClientError on put_bucket_lifecycle_configuration
        WHEN configure_bucket_lifecycle is called
        THEN StorageError is raised.
        """
        mock_client = MagicMock()
        mock_client.put_bucket_lifecycle_configuration.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "S3 error"}},
            "put_bucket_lifecycle_configuration",
        )
        with patch("src.shared.storage.boto3.client", return_value=mock_client):
            with pytest.raises(StorageError):
                await configure_bucket_lifecycle(
                    endpoint_url="https://r2.example.com",
                    access_key="ak",
                    secret_key="sk",
                    bucket="test-bucket",
                )

    async def test_lifecycle_passes_botocore_config(self):
        """GIVEN configure_bucket_lifecycle is called
        THEN boto3.client receives a botocore.config.Config with
        connect_timeout=5, read_timeout=10, retries={'max_attempts': 3}.
        """
        with patch("src.shared.storage.boto3.client") as mock_boto3:
            mock_boto3.return_value = MagicMock()
            await configure_bucket_lifecycle(
                endpoint_url="https://r2.example.com",
                access_key="ak",
                secret_key="sk",
                bucket="test-bucket",
            )

        config = mock_boto3.call_args.kwargs["config"]
        assert isinstance(config, botocore.config.Config)
        assert config.connect_timeout == 5
        assert config.read_timeout == 10
        assert config.retries == {"max_attempts": 3}
