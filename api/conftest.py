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
"""

import src.features.auth.infrastructure.models  # noqa: F401 — registers User, RefreshToken