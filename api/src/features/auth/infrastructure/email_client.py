"""Backward-compatible public email delivery imports.

Implementation is split into protocol, bounded execution, Resend transport,
and composition modules.
"""

from src.features.auth.infrastructure.email_composition import ResendEmailClient, build_email_client
from src.features.auth.infrastructure.email_execution import (
    BoundedDeliveryPool, _in_flight_count, _reset_pool_for_tests, shutdown_delivery_pool,
)
from src.features.auth.infrastructure.email_protocol import DevEmailClient, EmailClient, SendResult

__all__ = ["BoundedDeliveryPool", "DevEmailClient", "EmailClient", "ResendEmailClient", "SendResult", "build_email_client", "shutdown_delivery_pool"]
