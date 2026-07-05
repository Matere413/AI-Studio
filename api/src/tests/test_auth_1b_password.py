"""Slice 1b — Argon2Hasher (task 1b-1).

Covers api-security spec: Argon2id Password Hashing with
``time_cost=3, memory_cost=64*1024, parallelism=2``, constant-time verify,
and the DUMMY_HASH used for login timing-attack mitigation.

These tests are written FIRST (RED) — the implementation
``src/features/auth/infrastructure/password_hasher.py`` does not exist yet.
"""

from __future__ import annotations

import re
import time

import pytest
from argon2 import Type
from argon2.exceptions import VerifyMismatchError

from src.features.auth.infrastructure.password_hasher import (
    Argon2Hasher,
    DUMMY_HASH,
)


class TestArgon2HasherParams:
    """The hasher MUST use the spec-mandated argon2id parameters."""

    def test_hash_produces_argon2id_format(self):
        """GIVEN a password
        WHEN hashed
        THEN the result starts with ``$argon2id$`` (per api-security spec).
        """
        hasher = Argon2Hasher()
        h = hasher.hash("CorrectHorse42!")
        assert h.startswith("$argon2id$"), f"expected argon2id, got: {h[:20]}"

    def test_hash_encodes_time_cost_3(self):
        """GIVEN a hashed password
        WHEN the encoded parameters are inspected
        THEN ``t=3`` (time_cost=3) appears in the hash.
        """
        hasher = Argon2Hasher()
        h = hasher.hash("CorrectHorse42!")
        assert "t=3" in h, f"expected t=3 in hash: {h}"

    def test_hash_encodes_memory_cost_64mb(self):
        """GIVEN a hashed password
        WHEN the encoded parameters are inspected
        THEN ``m=65536`` (memory_cost=64*1024) appears in the hash.
        """
        hasher = Argon2Hasher()
        h = hasher.hash("CorrectHorse42!")
        assert "m=65536" in h, f"expected m=65536 in hash: {h}"

    def test_hash_encodes_parallelism_2(self):
        """GIVEN a hashed password
        WHEN the encoded parameters are inspected
        THEN ``p=2`` (parallelism=2) appears in the hash.
        """
        hasher = Argon2Hasher()
        h = hasher.hash("CorrectHorse42!")
        assert "p=2" in h, f"expected p=2 in hash: {h}"

    def test_hasher_uses_argon2id_type(self):
        """GIVEN the hasher instance
        WHEN its type is queried
        THEN it is configured for argon2id (not argon2i or argon2d)."""
        from argon2 import PasswordHasher

        hasher = Argon2Hasher()
        # The underlying PasswordHasher's type defaults to ID; confirm by
        # inspecting a produced hash which always encodes the variant.
        h = hasher.hash("whatever-password-1")
        # The variant is the first segment after the ``$argon2`` prefix.
        match = re.match(r"^\$argon2(id|i|d)\$", h)
        assert match is not None
        assert match.group(1) == "id"


class TestArgon2HasherHashAndVerify:
    """hash() + verify() round-trip and constant-time behaviour."""

    def test_verify_accepts_correct_password(self):
        """GIVEN a hash of a known password
        WHEN verified with that password
        THEN it returns True.
        """
        hasher = Argon2Hasher()
        h = hasher.hash("CorrectHorse42!")
        assert hasher.verify(h, "CorrectHorse42!") is True

    def test_verify_rejects_wrong_password(self):
        """GIVEN a hash of a known password
        WHEN verified with a different password
        THEN it returns False (not raise).
        """
        hasher = Argon2Hasher()
        h = hasher.hash("CorrectHorse42!")
        assert hasher.verify(h, "wrong-password-99") is False

    def test_hash_is_salt_randomised(self):
        """GIVEN the same password hashed twice
        WHEN the two hashes are compared
        THEN they differ (argon2id per-hash salt).
        """
        hasher = Argon2Hasher()
        h1 = hasher.hash("SamePassword123")
        h2 = hasher.hash("SamePassword123")
        assert h1 != h2, "hashes must differ due to per-hash salt"

    def test_verify_two_distinct_hashes_returns_independently(self):
        """GIVEN two stored hashes
        WHEN credentials are validated against each
        THEN the correct one verifies True and the wrong one False
        (constant-time comparison does not leak ordering)."""
        hasher = Argon2Hasher()
        h_alice = hasher.hash("AliceSecret42!")
        h_bob = hasher.hash("BobSecret42!!")
        # Alice's hash with Alice's password → True
        assert hasher.verify(h_alice, "AliceSecret42!") is True
        # Alice's hash with Bob's password → False
        assert hasher.verify(h_alice, "BobSecret42!!") is False
        # Bob's hash with Bob's password → True
        assert hasher.verify(h_bob, "BobSecret42!!") is True


class TestDummyHash:
    """DUMMY_HASH for login timing-attack mitigation.

    On email-not-found, login MUST run ``verify(DUMMY_HASH, password)`` to
    burn the same time as a real verify, then return invalid_credentials.
    Both branches (missing email vs wrong password) MUST be
    indistinguishable in timing.
    """

    def test_dummy_hash_is_argon2id(self):
        """GIVEN the module's DUMMY_HASH constant
        WHEN inspected
        THEN it is a valid argon2id hash string.
        """
        assert DUMMY_HASH.startswith("$argon2id$"), (
            f"DUMMY_HASH must be argon2id, got: {DUMMY_HASH[:20]}"
        )

    def test_dummy_hash_uses_same_params(self):
        """GIVEN the DUMMY_HASH
        WHEN its encoded params are inspected
        THEN it carries the same t=3, m=65536, p=2 as real hashes.
        """
        assert "t=3" in DUMMY_HASH
        assert "m=65536" in DUMMY_HASH
        assert "p=2" in DUMMY_HASH

    def test_dummy_hash_is_module_level_constant(self):
        """GIVEN DUMMY_HASH
        WHEN the module is imported twice
        THEN it is the same object instance (fixed at boot, not recomputed).
        """
        import src.features.auth.infrastructure.password_hasher as mod

        assert mod.DUMMY_HASH is DUMMY_HASH

    def test_verify_dummy_hash_returns_false_for_arbitrary_password(self):
        """GIVEN DUMMY_HASH and an arbitrary submitted password
        WHEN verify(DUMMY_HASH, password)
        THEN it returns False (the login-no-user branch relies on this).
        """
        hasher = Argon2Hasher()
        assert hasher.verify(DUMMY_HASH, "any-password-at-all") is False

    def test_dummy_verify_burns_time_comparable_to_real_verify(self):
        """GIVEN the timing-attack mitigation requirement
        WHEN a dummy verify (no user) vs a real verify (wrong password) run
        THEN both take a comparable amount of time (within a loose factor).

        This is a coarse equivalence test — not a constant-time proof, but it
        catches the regression where the dummy branch returns instantly.
        Both branches MUST execute argon2id.verify to be indistinguishable.
        """
        hasher = Argon2Hasher()
        real_hash = hasher.hash("SomeRealPassword123")

        # Time the dummy-verify branch (no user found)
        t0 = time.monotonic()
        _ = hasher.verify(DUMMY_HASH, "SomeRealPassword123")
        dummy_elapsed = time.monotonic() - t0

        # Time the real-verify-wrong-password branch (user found, wrong pw)
        t0 = time.monotonic()
        _ = hasher.verify(real_hash, "SomeRealPassword123_wrong")
        real_elapsed = time.monotonic() - t0

        # Both should execute an argon2id.verify (≈ same order of magnitude).
        # We assert the dummy branch is NOT instant (< 1ms would indicate it
        # short-circuited). The real branch may be marginally faster because
        # argon2id verify on a real hash with a wrong password still hashes
        # the candidate. Allow a generous factor so this is CI-stable.
        assert dummy_elapsed > 0.001, (
            f"dummy verify appears to short-circuit (elapsed={dummy_elapsed:.4f}s)"
        )
        # Both within 5x of each other (loose; argon2 timings vary with load).
        ratio = max(dummy_elapsed, real_elapsed) / max(
            min(dummy_elapsed, real_elapsed), 1e-9
        )
        assert ratio < 5.0, (
            f"timing divergence too large: dummy={dummy_elapsed:.4f}s "
            f"real={real_elapsed:.4f}s ratio={ratio:.2f}"
        )