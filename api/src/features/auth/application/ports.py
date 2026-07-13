"""Inward-facing application ports for the auth feature.

Hexagonal dependency direction: the application layer defines the ports it
needs, and the infrastructure layer satisfies them structurally (duck-typed
Protocol). The application layer must NOT import or type against concrete
infrastructure classes for its policy decisions.

Ports defined here:
- :class:`DeliveredChallengeQuery` — the read-only query the save-gate policy
  uses to decide whether an unverified user has a delivered verification
  challenge on record. The infrastructure ``EmailVerificationStore``
  satisfies this Protocol structurally (it exposes
  ``has_delivered_challenge(user_id) -> bool``).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class DeliveredChallengeQuery(Protocol):
    """Read-only query: does ``user_id`` have a delivered, unconsumed,
    unexpired verification challenge on record?

    The save-gate policy (``enforce_save_gate``) consults this port — NOT a
    concrete infrastructure store — so the application layer depends only on
    the contract it defines. Any object exposing this method satisfies the
    port structurally (the production ``EmailVerificationStore`` and any
    test stub alike).
    """

    def has_delivered_challenge(self, user_id: str) -> bool: ...


__all__ = ["DeliveredChallengeQuery"]