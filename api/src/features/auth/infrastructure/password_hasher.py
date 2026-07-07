"""Argon2id password hasher + DUMMY_HASH for login timing-attack mitigation.

Spec: api-security — Argon2id Password Hashing with ``time_cost=3``,
``memory_cost=64*1024``, ``parallelism=2``. Plaintext passwords are NEVER
stored or logged; verification uses argon2's constant-time comparison.

DUMMY_HASH (binding from design.md):
    A fixed argon2id hash generated at module import time. On login when the
    email is NOT found in the database, ``verify(DUMMY_HASH, password)`` is
    run to burn the same wall-clock time as a real verify, then
    ``invalid_credentials`` is returned. Both branches (missing email vs
    wrong password) thus take indistinguishable time, preventing
    email-enumeration via response timing.

The DUMMY_HASH is computed ONCE at module load (fixed at boot) so every
login attempt with a missing email pays the same hash cost. It is a hash of
a fixed dummy plaintext; ``verify`` against any other plaintext returns
``False`` (the candidate never matches), but the argon2id work is done.
"""

from __future__ import annotations

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError

# Spec-mandated argon2id parameters (binding).
_TIME_COST: int = 3
_MEMORY_COST: int = 64 * 1024  # 64 MiB
_PARALLELISM: int = 2

# A single PasswordHasher configured with the binding parameters. argon2-cffi
# defaults to Type.ID, which is what we want, but we set it explicitly so the
# variant is unambiguous and survives any future upstream default change.
_HASHER: PasswordHasher = PasswordHasher(
    time_cost=_TIME_COST,
    memory_cost=_MEMORY_COST,
    parallelism=_PARALLELISM,
    type=Type.ID,
)

# A fixed dummy plaintext used to precompute DUMMY_HASH at module import.
# The value is irrelevant — it is NEVER used to authenticate — it only needs
# to be a stable string so the hash is deterministic across processes that
# share this source file. Any candidate password verified against DUMMY_HASH
# will fail (VerifyMismatchError), which is exactly the no-user branch we
# want: argon2id.verify runs the full work, then returns False.
_DUMMY_PLAINTEXT: str = "ai-studio-dummy-do-not-use-for-login"


def _compute_dummy_hash() -> str:
    """Compute the DUMMY_HASH once at module import (fixed at boot).

    This is intentionally computed at import time (not lazily) so the cost
    is paid once when the module loads — request-time login calls just
    verify against it, paying only the verify cost (the same cost as a real
    wrong-password verify).
    """
    return _HASHER.hash(_DUMMY_PLAINTEXT)


DUMMY_HASH: str = _compute_dummy_hash()
"""Fixed argon2id hash used for login timing-attack mitigation.

When a login attempt uses an email that is NOT in the database, the login
use case runs ``Argon2Hasher().verify(DUMMY_HASH, submitted_password)`` to
burn the same wall-clock time as a real verify against a stored hash, then
raises ``InvalidCredentialsError``. This makes the "no such email" branch
indistinguishable from the "wrong password" branch by timing.
"""


class Argon2Hasher:
    """Argon2id password hasher with spec-mandated parameters.

    Provides ``hash`` and ``verify``. ``verify`` returns ``True``/``False``
    rather than raising on mismatch — the login use case relies on the
    boolean return to keep its control flow linear.
    """

    def __init__(self) -> None:
        # Use the module-level _HASHER so the (heavy) argon2id parameters are
        # configured exactly once per process. Creating a PasswordHasher is
        # cheap (it stores parameters), so per-instance reuse is fine.
        self._hasher: PasswordHasher = _HASHER

    def hash(self, password: str) -> str:
        """Hash a plaintext password with argon2id.

        Args:
            password: The plaintext password. MUST NOT be logged or stored.

        Returns:
            An argon2id-encoded hash string (``$argon2id$...``) suitable for
            persistence in ``users.password_hash``.

        Each call produces a distinct hash (per-hash random salt).
        """
        return self._hasher.hash(password)

    def verify(self, hash: str, password: str) -> bool:
        """Verify a plaintext against an argon2id hash in constant time.

        Args:
            hash: The stored argon2id hash string.
            password: The candidate plaintext password.

        Returns:
            ``True`` when the password matches the hash, ``False`` otherwise
            (including when ``hash`` is the DUMMY_HASH and any candidate is
            supplied — this is the login-no-user timing mitigation path).
        """
        try:
            self._hasher.verify(hash, password)
            return True
        except VerifyMismatchError:
            return False


__all__ = ["Argon2Hasher", "DUMMY_HASH"]