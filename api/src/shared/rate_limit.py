"""In-memory sliding-window rate limiter (slice 4 — task 4-1).

Hand-rolled (no ``slowapi`` dependency) per the design's open question:
in-memory per-container state is acceptable for MVP scale and resets on
cold-start, which is fine for the Modal serverless context. A SQLite-backed
limiter is the documented escape hatch if a persistent cross-container
budget becomes necessary.

Limits (binding — from ``api-security`` spec + slice 4 brief):

    /auth/login              5 / min  per IP   + per email
    /auth/register           3 / min  per IP
    /auth/verify-email       5 / min  per IP
    /auth/resend-verification 3 / min  per user (user_id, NOT IP)

When a bucket is exhausted the limiter raises
:class:`~src.shared.errors_auth.RateLimitedError` carrying a ``retry_after``
hint (seconds until the oldest request in the window falls out), which the
global error handler emits as the ``Retry-After`` response header.

Thread safety: a module-level :class:`threading.Lock` guards the bucket map.
The auth use cases run in a thread pool (``asyncio.to_thread``); the limiter
``check`` runs in the async endpoint BEFORE the offload, but the lock is kept
anyway so concurrent requests from the asyncio event loop are safe.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque

from src.shared.errors_auth import RateLimitedError

# ─── Constants ────────────────────────────────────────────────────────────────

WINDOW_SECONDS = 60  # 1 minute (the spec rates are "per minute")

# ─── Limits per endpoint + dimension ──────────────────────────────────────────

LOGIN_LIMIT = 5
REGISTER_LIMIT = 3
VERIFY_EMAIL_LIMIT = 5
RESEND_VERIFICATION_LIMIT = 3


def _now() -> float:
    """Indirection over :func:`time.monotonic` so tests can monkeypatch the
    clock without touching the global ``time`` module."""
    return time.monotonic()


class RateLimiter:
    """Sliding-window per-key counter.

    Each key maps to a deque of monotonic timestamps representing the
    requests that are still inside the window. On every ``check``:

    1. Drop timestamps older than ``now - WINDOW_SECONDS`` (left-pop).
    2. If the remaining deque length is >= ``limit``, the bucket is
       exhausted → raise :class:`RateLimitedError` with a ``retry_after``
       hint computed as the time until the oldest in-window request falls
       out of the window.
    3. Otherwise append ``now`` and return (the request is allowed).

    The limiter is intentionally simple: no persistence, no clustering, no
    background eviction. Stale keys accumulate lazily — a key that has been
    quiet for ``WINDOW_SECONDS`` is fully drained on its next ``check``.
    Memory is bounded in practice by the number of distinct keys (IPs +
    emails + user_ids) hitting the auth endpoints, which is small for MVP.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int) -> None:
        """Record a request for ``key`` and raise when the budget is spent.

        Args:
            key: The bucket identifier (e.g. ``"login:ip:1.2.3.4"``).
            limit: The maximum number of requests allowed inside the window.

        Raises:
            RateLimitedError: when the key has already consumed ``limit``
                requests within the last ``WINDOW_SECONDS``. The error
                carries ``retry_after`` (seconds) so the client knows how
                long to wait before retrying.
        """
        now = _now()
        cutoff = now - WINDOW_SECONDS
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket
            # Drop timestamps that fell out of the window (lazy eviction).
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                # Bucket exhausted. retry_after = time until the OLDEST
                # in-window request falls out of the window.
                oldest = bucket[0]
                retry_after = max(1, int(oldest + WINDOW_SECONDS - now) + 1)
                raise RateLimitedError(retry_after=retry_after)
            bucket.append(now)

    def reset(self) -> None:
        """Clear every bucket. Test-only hook so each test starts clean."""
        with self._lock:
            self._buckets.clear()


# ─── Module-level singleton ───────────────────────────────────────────────────
#
# A single instance is shared across all requests in a container. The state
# is per-container and resets on cold-start (acceptable per the design).

RATE_LIMITER = RateLimiter()


# ─── Per-endpoint helpers ─────────────────────────────────────────────────────
#
# These wrap the singleton with the binding-specific key prefixes + limits so
# the router endpoints stay one-liners. Each returns ``None`` on success and
# raises ``RateLimitedError`` on exhaustion.


def check_login(ip: str | None, email: str) -> None:
    """Enforce the login limits: 5/min per IP AND 5/min per email.

    Both buckets are checked. If EITHER is exhausted, the request is
    rejected. The IP bucket is checked first (most common brute-force
    vector), then the email bucket.

    ``ip`` may be ``None`` (e.g. a request with no X-Forwarded-For and no
    ``request.client``); in that case the IP bucket is skipped — only the
    email bucket is enforced. This is the conservative behaviour: never
    silently allow an unkeyed flood.
    """
    if ip is not None:
        RATE_LIMITER.check(f"login:ip:{ip}", LOGIN_LIMIT)
    RATE_LIMITER.check(f"login:email:{email}", LOGIN_LIMIT)


def check_register(ip: str | None) -> None:
    """Enforce the register limit: 3/min per IP."""
    if ip is None:
        return
    RATE_LIMITER.check(f"register:ip:{ip}", REGISTER_LIMIT)


def check_verify_email(ip: str | None) -> None:
    """Enforce the verify-email limit: 5/min per IP."""
    if ip is None:
        return
    RATE_LIMITER.check(f"verify-email:ip:{ip}", VERIFY_EMAIL_LIMIT)


def check_resend_verification(user_id: str) -> None:
    """Enforce the resend-verification limit: 3/min per user (NOT per IP)."""
    RATE_LIMITER.check(f"resend:user:{user_id}", RESEND_VERIFICATION_LIMIT)


__all__ = [
    "RATE_LIMITER",
    "RateLimiter",
    "WINDOW_SECONDS",
    "LOGIN_LIMIT",
    "REGISTER_LIMIT",
    "VERIFY_EMAIL_LIMIT",
    "RESEND_VERIFICATION_LIMIT",
    "check_login",
    "check_register",
    "check_verify_email",
    "check_resend_verification",
]