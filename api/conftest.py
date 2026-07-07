"""Root pytest configuration for the AI-Studio API.

Ensures all ORM models are registered on the shared ``Base.metadata`` before
any test calls ``Base.metadata.create_all`` / ``Project.metadata.create_all``.

After the ``add-auth`` change, ``Project.owner_id`` is a real FK to
``users.id``. The ``User`` and ``RefreshToken`` models live in
``src.features.auth.infrastructure.models`` and register themselves on
``Base.metadata`` at import time. Tests that create the ``projects`` table
without importing the auth models would hit
``NoReferencedTableError: table 'users'``. Importing them here once guarantees
the metadata is complete for every test in the suite.

Slice 4 added a process-wide in-memory rate limiter
(:mod:`src.shared.rate_limit`). The limiter's buckets persist across tests
in the same process, so a slice-1b/2 test that hits /auth/login six times
from the test client's IP would trip the slice-4 limit mid-test. This
conftest resets the limiter before every test so each test starts with
empty buckets — the slice-4 rate-limit tests still pass because they
exhaust the buckets within a single test.
"""

import pytest

import src.features.auth.infrastructure.models  # noqa: F401 — registers User, RefreshToken


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear the module-level RATE_LIMITER before every test.

    The limiter is a process-wide singleton (per-container in prod). Without
    this reset, tests that issue many auth requests from the same client IP
    (the httpx TestClient uses ``testclient`` / ``127.0.0.1``) would trip
    the slice-4 limits mid-test and fail with spurious 429s.
    """
    from src.shared.rate_limit import RATE_LIMITER

    RATE_LIMITER.reset()