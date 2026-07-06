"""Custom exception hierarchy and FastAPI global error handler.

Provides AppError base class with structured error fields and
subclasses for known error conditions. The global handler
``register_app_error_handlers`` should be called at app startup
to convert AppError instances into structured JSON responses.
"""

import re

from fastapi import FastAPI
from fastapi.responses import JSONResponse


# Regex patterns for sanitizing error details
_PATH_PATTERN = re.compile(r"/[a-zA-Z0-9_\-./]+")
_NODE_REF_PATTERN = re.compile(r"\bnode \d+(?:, [A-Za-z0-9_]+)?")


def _sanitize_error_detail(detail: str) -> str:
    """Strip internal paths and node IDs from an error detail string.

    Removes:
    - Absolute paths (``/root/ComfyUI/...``, ``/var/...``, etc.)
    - ``node {N}`` references that expose internal ComfyUI topology

    The original message structure is preserved; only the sensitive
    fragments are removed.
    """
    if not detail:
        return detail

    # Remove node {N} references
    result = _NODE_REF_PATTERN.sub("", detail)

    # Remove absolute paths (anything starting with /)
    result = _PATH_PATTERN.sub(lambda m: "[redacted]" if m.group(0).startswith("/") else m.group(0), result)

    # Clean up double spaces left by removals
    result = re.sub(r" {2,}", " ", result).strip()

    # Clean up trailing/leading artifacts
    result = result.replace("(, ", "(").replace(", )", ")").replace("()", "")
    result = re.sub(r"\s*\[\s*redacted\s*\]", " [redacted]", result)

    return result


class AppError(Exception):
    """Base class for structured application errors.

    Attributes:
        status_code: HTTP status code for the response.
        code: Machine-readable error code (e.g. ``model_not_allowed``).
        user_message: Human-readable detail for the response body.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        user_message: str,
    ):
        self.status_code = status_code
        self.code = code
        self.user_message = user_message
        super().__init__(self.user_message)

    def __str__(self) -> str:
        return self.user_message


class ModelNotAllowedError(AppError):
    """Raised when a requested model is not in the allowed whitelist (400)."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        super().__init__(
            status_code=400,
            code="model_not_allowed",
            user_message=f"Model '{model_id}' is not in the allowed whitelist.",
        )


class ModelNotCachedError(AppError):
    """Raised when a model is not cached in the Modal volume (500)."""

    def __init__(self, filename: str):
        self.filename = filename
        super().__init__(
            status_code=500,
            code="model_not_cached",
            user_message=f"Model '{filename}' is not cached.",
        )


class UnsupportedWorkflowError(AppError):
    """Raised when a requested workflow name is not supported (422)."""

    def __init__(self, workflow_name: str):
        self.workflow_name = workflow_name
        super().__init__(
            status_code=422,
            code="unsupported_workflow",
            user_message=f"Workflow '{workflow_name}' is not supported.",
        )


class SessionMismatchError(AppError):
    """Raised when artifact ownership does not match the request session (403)."""

    def __init__(self, request_session: str, owner_session: str):
        self.request_session = request_session
        self.owner_session = owner_session
        super().__init__(
            status_code=403,
            code="session_mismatch",
            user_message=(
                f"Session mismatch: request session '{request_session}' "
                f"does not match artifact owner session '{owner_session}'."
            ),
        )


def register_app_error_handlers(app: FastAPI) -> None:
    """Register the global ``AppError`` exception handler on a FastAPI app.

    All ``AppError`` subclasses raised during request processing are
    caught and returned as ``JSONResponse`` with the structured
    ``{"error": {"code": ..., "detail": ...}}`` shape.

    When an error carries a ``retry_after`` attribute (e.g.
    :class:`~src.shared.errors_auth.RateLimitedError`), the response also
    includes a ``Retry-After`` header (RFC 6585 §4).
    """
    @app.exception_handler(AppError)
    async def _app_error_handler(request, exc: AppError) -> JSONResponse:
        headers: dict[str, str] = {}
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is not None:
            headers["Retry-After"] = str(int(retry_after))
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "detail": exc.user_message,
                }
            },
            headers=headers,
        )
