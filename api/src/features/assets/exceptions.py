"""Custom domain exceptions for the Assets feature.

Provides typed exception classes so the router can map them to
appropriate HTTP status codes without stringly-typed errors.
"""


class ProjectNotFoundError(Exception):
    """Raised when a Project UUID does not match any row (→ 404)."""


class ProjectOwnershipError(Exception):
    """Raised when the caller's session does not match the project's
    ``session_id`` (→ 403)."""


class AssetNotFoundError(Exception):
    """Raised when an Asset UUID does not match any row (→ 404)."""


class StorageNotConfiguredError(Exception):
    """Raised when R2Storage is not configured but an upload ticket is
    requested (→ 503)."""


class AssetNotReadyError(Exception):
    """Raised when an asset is active and owned but not yet finalized
    (upload_status != 'finalized' or finalized_at is None).  The caller
    should wait for the upload to complete or prompt the user to finalize
    the asset (→ 409 Conflict)."""


class StorageOperationError(Exception):
    """Raised when the underlying storage layer (R2) fails during
    presigned URL generation (→ 502)."""
