"""Bounded execution and lifecycle management for email delivery."""

from __future__ import annotations

import concurrent.futures
import os
import threading
from collections.abc import Callable

from src.shared.telemetry import capture_delivery_late_resolved

DEFAULT_POOL_MAX_WORKERS = 4
DEFAULT_POOL_MAX_QUEUED = 64
DEFAULT_SUBMIT_TIMEOUT_MS = 0


def _positive_env(name: str, default: int, *, allow_zero: bool = False) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 or (allow_zero and value == 0) else default


class BoundedDeliveryPool:
    """Bound running and queued delivery work; reject work after shutdown."""

    def __init__(self, *, max_workers: int, max_queued: int, submit_timeout_ms: int) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="resend-send"
        )
        self._capacity = max(1, max_workers + max_queued)
        self._permits = threading.BoundedSemaphore(self._capacity)
        self._submit_timeout_s = max(0, submit_timeout_ms) / 1000
        self._shutting_down = False
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def submit(self, fn: Callable, *args) -> concurrent.futures.Future | None:
        with self._lock:
            if self._shutting_down:
                return None
        acquired = self._permits.acquire(
            blocking=self._submit_timeout_s > 0, timeout=self._submit_timeout_s
        ) if self._submit_timeout_s > 0 else self._permits.acquire(blocking=False)
        if not acquired:
            return None
        try:
            future = self._executor.submit(fn, *args)
        except RuntimeError:
            self._permits.release()
            return None
        future.add_done_callback(lambda _: self._permits.release())
        return future

    def shutdown(self) -> None:
        """Stop admission, cancel queued jobs, and never wait for running I/O."""
        with self._lock:
            if self._shutting_down:
                return
            self._shutting_down = True
        self._executor.shutdown(wait=False, cancel_futures=True)


_pool: BoundedDeliveryPool | None = None
_pool_lock = threading.Lock()
_in_flight = 0
_in_flight_lock = threading.Lock()


def get_delivery_pool() -> BoundedDeliveryPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = BoundedDeliveryPool(
                max_workers=_positive_env("RESEND_SEND_POOL_MAX_WORKERS", DEFAULT_POOL_MAX_WORKERS),
                max_queued=_positive_env("RESEND_SEND_POOL_MAX_QUEUED", DEFAULT_POOL_MAX_QUEUED, allow_zero=True),
                submit_timeout_ms=_positive_env("RESEND_SEND_SUBMIT_TIMEOUT_MS", DEFAULT_SUBMIT_TIMEOUT_MS, allow_zero=True),
            )
        return _pool


def shutdown_delivery_pool() -> None:
    """Application lifecycle hook for delivery-only graceful shutdown."""
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is not None:
        pool.shutdown()


def _in_flight_count() -> int:
    with _in_flight_lock:
        return _in_flight


def _increment_in_flight() -> None:
    global _in_flight
    with _in_flight_lock:
        _in_flight += 1


def _decrement_in_flight() -> None:
    global _in_flight
    with _in_flight_lock:
        _in_flight -= 1


def observe_late_resolution(future: concurrent.futures.Future, token_prefix: str) -> None:
    try:
        result = future.result()
        late_success = isinstance(result, dict) and result.get("ok") is True
    except Exception:
        late_success = False
    capture_delivery_late_resolved(
        provider="resend", late_success=late_success, token_prefix=token_prefix
    )


def _reset_pool_for_tests() -> None:
    shutdown_delivery_pool()
    global _in_flight
    with _in_flight_lock:
        _in_flight = 0
