"""Logical idempotency of the Resend Idempotency-Key — judgment-day finding #3.

The contract: the ``Idempotency-Key`` sent to Resend MUST be STABLE for the
same verification challenge / logical delivery (including retries), and a
NEW challenge MUST get a NEW key. Previously the key was a fresh UUID per
HTTP attempt, so a retry of an uncertain-timeout send would NOT be deduped
by Resend → a hung-then-retried send could double-deliver a verification
link.

The fix threads a stable, non-sensitive ``delivery_id`` (the verification
row PK — a UUID) from the store / use case into ``send_verification``. The
client derives the ``Idempotency-Key`` deterministically from it:
- SAME challenge (same ``delivery_id``) → SAME key, across retries.
- NEW challenge (new ``delivery_id``) → NEW key.
- The raw token / email are NEVER used as the key.

These tests assert the three required scenarios:
1. Same challenge → same key (across retries / re-issues).
2. New challenge → different key.
3. Uncertain retry behavior — a re-issue of the SAME challenge passes the
   same key (so Resend dedupes), while the fallback (no ``delivery_id``)
   uses a fresh UUID per call (preserving the original
   at-most-once-per-HTTP-attempt behaviour).
"""

from __future__ import annotations

import pytest

from src.features.auth.infrastructure.email_client import (
    ResendEmailClient,
)
from src.features.auth.infrastructure.resend_transport import derive_idempotency_key


# ─── derive_idempotency_key — the pure derivation ─────────────────────────────


class TestDeriveIdempotencyKey:
    """The pure derivation function — the contract in isolation."""

    def test_same_delivery_id_yields_same_key(self):
        """GIVEN the same delivery_id twice
        WHEN derive_idempotency_key is called for each
        THEN both keys are identical — a retry of the same logical delivery
        gets the same key so Resend dedupes it."""
        key1 = derive_idempotency_key("challenge-aaa")
        key2 = derive_idempotency_key("challenge-aaa")
        assert key1 == key2, "same challenge → same key"

    def test_different_delivery_ids_yield_different_keys(self):
        """GIVEN two different delivery_ids
        WHEN derive_idempotency_key is called for each
        THEN the keys differ — a new challenge gets a new key."""
        key1 = derive_idempotency_key("challenge-aaa")
        key2 = derive_idempotency_key("challenge-bbb")
        assert key1 != key2, "new challenge → new key"

    def test_none_delivery_id_falls_back_to_uuid_and_is_unique_per_call(self):
        """GIVEN no delivery_id (older caller / test)
        WHEN derive_idempotency_key is called twice
        THEN each call returns a DIFFERENT uuid (the fallback preserves the
        original at-most-once-per-HTTP-attempt behaviour — a retry without a
        stable id is NOT deduped, matching the pre-fix behaviour)."""
        key1 = derive_idempotency_key(None)
        key2 = derive_idempotency_key(None)
        assert key1 != key2, "no delivery_id → fresh uuid per call (fallback)"
        # Both are uuid-like (36 chars, hyphenated).
        assert len(key1) == 36 and key1.count("-") == 4
        assert len(key2) == 36 and key2.count("-") == 4

    def test_empty_delivery_id_falls_back_to_uuid(self):
        """GIVEN an empty-string delivery_id
        WHEN derive_idempotency_key is called
        THEN it falls back to a uuid (an empty id is not a stable handle)."""
        key = derive_idempotency_key("")
        assert len(key) == 36 and key.count("-") == 4, "empty → uuid fallback"

    def test_key_does_not_leak_raw_token_or_email(self):
        """GIVEN a delivery_id that is the verification row PK (a UUID)
        WHEN derive_idempotency_key is called
        THEN the returned key is the PK itself (non-sensitive) and NEVER
        contains the raw token / email — those are never passed to the
        derivation. This guards the no-sensitive-key contract."""
        raw_token = "supersecret-raw-token-1234567890ABCDEF"
        email = "leak@example.io"
        delivery_id = "row-pk-uuid-1234"
        key = derive_idempotency_key(delivery_id)
        assert raw_token not in key, "raw token MUST NOT be in the key"
        assert email not in key, "email MUST NOT be in the key"
        assert key == delivery_id, "the key IS the non-sensitive PK"


# ─── ResendEmailClient — the key is what hits the wire ───────────────────────


class TestResendClientIdempotencyKey:
    """The ResendEmailClient threads ``delivery_id`` → ``Idempotency-Key``.
    A controllable fake transport records the key each call sent so the
    stability contract is provable at the client seam (not just the pure
    function)."""

    def _client_recording_keys(self, keys_out: list[str]):
        """Build a ResendEmailClient whose injected transport records the
        Idempotency-Key into ``keys_out`` and returns success (so the
        bounded-pool path resolves ``SendResult(success=True)``).

        The immutable request is the only transport input."""
        def _fake_send(request):
            keys_out.append(request.idempotency_key)
            return {"ok": True}

        return ResendEmailClient(
            api_key="re_test", from_email="noreply@test.io",
            app_base_url="https://app.test", send_transport=_fake_send,
        )

    def test_same_challenge_same_key_across_retries(self):
        """GIVEN the same delivery_id (same challenge) on multiple
        send_verification calls (retries / re-issues)
        WHEN the client sends each
        THEN every transport call receives the SAME Idempotency-Key — Resend
        will dedupe the retries for 24h, so a hung-then-retried send does not
        double-deliver."""
        keys: list[str] = []
        client = self._client_recording_keys(keys)

        client.send_verification(
            email="u@t.io", raw_token="tokA", delivery_id="challenge-aaa"
        )
        client.send_verification(
            email="u@t.io", raw_token="tokA", delivery_id="challenge-aaa"
        )
        client.send_verification(
            email="u@t.io", raw_token="tokA", delivery_id="challenge-aaa"
        )

        assert len(keys) == 3
        assert keys[0] == keys[1] == keys[2], (
            "retries of the SAME challenge MUST carry the same Idempotency-Key"
        )

    def test_new_challenge_different_key(self):
        """GIVEN two different delivery_ids (two different challenges)
        WHEN the client sends each
        THEN the two transport calls receive DIFFERENT Idempotency-Keys — a
        new resend challenge is a distinct logical delivery."""
        keys: list[str] = []
        client = self._client_recording_keys(keys)

        client.send_verification(
            email="u@t.io", raw_token="tokA", delivery_id="challenge-aaa"
        )
        client.send_verification(
            email="u@t.io", raw_token="tokB", delivery_id="challenge-bbb"
        )

        assert len(keys) == 2
        assert keys[0] != keys[1], (
            "a NEW challenge MUST carry a different Idempotency-Key"
        )

    def test_no_delivery_id_falls_back_to_unique_key_per_call(self):
        """GIVEN no delivery_id (older caller / test)
        WHEN the client sends twice
        THEN each transport call receives a DIFFERENT (uuid) key — the
        fallback preserves the original at-most-once-per-HTTP-attempt
        behaviour, so existing callers that do not thread the id keep
        working without accidental cross-call dedup."""
        keys: list[str] = []
        client = self._client_recording_keys(keys)

        client.send_verification(email="u@t.io", raw_token="tokA")
        client.send_verification(email="u@t.io", raw_token="tokA")

        assert len(keys) == 2
        assert keys[0] != keys[1], (
            "no delivery_id → fresh uuid per call (backward-compatible fallback)"
        )

    def test_delivery_id_not_sent_as_raw_token_or_email(self):
        """GIVEN a delivery_id + a raw_token + an email
        WHEN the client sends
        THEN the Idempotency-Key recorded is the delivery_id (the non-
        sensitive PK), NOT the raw token or the email. The transport fake
        records only the key; we assert the raw token / email never appear
        in it (the key is the PK, a non-sensitive UUID)."""
        keys: list[str] = []
        client = self._client_recording_keys(keys)

        raw_token = "supersecret-raw-token-1234567890ABCDEF"
        email = "leak@example.io"
        delivery_id = "row-pk-uuid-1234"
        client.send_verification(
            email=email, raw_token=raw_token, delivery_id=delivery_id
        )

        assert keys[0] == delivery_id
        assert raw_token not in keys[0], "raw token MUST NOT be the key"
        assert email not in keys[0], "email MUST NOT be the key"
