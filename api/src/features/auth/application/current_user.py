"""The authenticated-user value object (application-layer domain type).

``CurrentUser`` is the application-layer representation of the authenticated
user: the user id, email, and the LIVE ``email_verified`` flag reloaded from
the database. It lives in the APPLICATION layer (not presentation) so that
use cases, the save-gate policy, and the presentation dependency layer can
all depend on it without a presentation → application → presentation import
cycle.

Presentation imports it (hexagonal direction: presentation → application)
and re-exports it for backward-compat with the many modules that already
import it from ``presentation.dependencies``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated user resolved by the auth dependency.

    A frozen dataclass so it is safe to share across the request lifecycle
    and store on ``request.state.user``.

    Attributes:
        id: The user's UUID (matches ``users.id`` and the JWT ``sub``).
        email: The user's email (reloaded from DB, not the JWT claim).
        email_verified: The CURRENT DB value of ``users.email_verified`` —
            reloaded on every request so the saving gate checks the live
            state, not a stale JWT claim.
    """

    id: str
    email: str
    email_verified: bool


__all__ = ["CurrentUser"]