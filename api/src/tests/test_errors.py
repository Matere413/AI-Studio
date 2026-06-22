"""Tests for the AppError exception hierarchy and global handler."""

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from src.shared.errors import (
    AppError,
    ModelNotAllowedError,
    ModelNotCachedError,
    SessionMismatchError,
    UnsupportedWorkflowError,
)


class TestAppErrorHierarchy:
    """Unit tests for AppError base class and subclasses."""

    # ── AppError base ──────────────────────────────────────────────

    def test_app_error_base_creates_with_required_fields(self):
        """GIVEN a status_code, code, and user_message
        WHEN creating an AppError
        THEN all fields are accessible.
        """
        exc = AppError(status_code=400, code="test_error", user_message="Something went wrong")
        assert exc.status_code == 400
        assert exc.code == "test_error"
        assert exc.user_message == "Something went wrong"

    def test_app_error_is_exception_subclass(self):
        """GIVEN an AppError
        WHEN raised
        THEN it can be caught as Exception.
        """
        exc = AppError(status_code=500, code="internal", user_message="Internal error")
        assert isinstance(exc, Exception)

    # ── ModelNotAllowedError ───────────────────────────────────────

    def test_model_not_allowed_error_has_400_status(self):
        """GIVEN a model_id that is not whitelisted
        WHEN creating ModelNotAllowedError
        THEN status_code is 400 and code is model_not_allowed.
        """
        exc = ModelNotAllowedError("forbidden_model.safetensors")
        assert exc.status_code == 400
        assert exc.code == "model_not_allowed"
        assert "forbidden_model.safetensors" in exc.user_message
        assert isinstance(exc, AppError)

    # ── ModelNotCachedError ────────────────────────────────────────

    def test_model_not_cached_error_has_500_status(self):
        """GIVEN a model that is not cached in the volume
        WHEN creating ModelNotCachedError
        THEN status_code is 500 and code is model_not_cached.
        """
        exc = ModelNotCachedError("missing_model.safetensors")
        assert exc.status_code == 500
        assert exc.code == "model_not_cached"
        assert "missing_model.safetensors" in exc.user_message
        assert isinstance(exc, AppError)

    # ── UnsupportedWorkflowError ───────────────────────────────────

    def test_unsupported_workflow_error_has_422_status(self):
        """GIVEN an unsupported workflow name
        WHEN creating UnsupportedWorkflowError
        THEN status_code is 422 and code is unsupported_workflow.
        """
        exc = UnsupportedWorkflowError("legacy_workflow")
        assert exc.status_code == 422
        assert exc.code == "unsupported_workflow"
        assert "legacy_workflow" in exc.user_message
        assert isinstance(exc, AppError)

    # ── SessionMismatchError ───────────────────────────────────────

    def test_session_mismatch_error_has_403_status(self):
        """GIVEN a session mismatch between request and artifact owner
        WHEN creating SessionMismatchError
        THEN status_code is 403 and code is session_mismatch.
        """
        exc = SessionMismatchError("session-123", "session-456")
        assert exc.status_code == 403
        assert exc.code == "session_mismatch"
        assert "session-123" in exc.user_message
        assert "session-456" in exc.user_message
        assert isinstance(exc, AppError)

    # ── str representation ─────────────────────────────────────────

    def test_app_error_str_returns_user_message(self):
        """GIVEN an AppError
        WHEN str() is called
        THEN the user_message is returned.
        """
        exc = AppError(status_code=400, code="err", user_message="User-visible message")
        assert str(exc) == "User-visible message"


class TestAppErrorGlobalHandler:
    """Integration tests for global AppError exception handler."""

    @pytest.fixture
    def app(self):
        """Create a minimal FastAPI app with the global handler."""
        from src.shared.errors import register_app_error_handlers
        app = FastAPI()
        register_app_error_handlers(app)

        @app.get("/test-model-not-allowed")
        def raise_model_not_allowed():
            raise ModelNotAllowedError("bad_model.safetensors")

        @app.get("/test-model-not-cached")
        def raise_model_not_cached():
            raise ModelNotCachedError("missing.safetensors")

        @app.get("/test-unsupported-workflow")
        def raise_unsupported_workflow():
            raise UnsupportedWorkflowError("legacy")

        @app.get("/test-session-mismatch")
        def raise_session_mismatch():
            raise SessionMismatchError("req-session", "owner-session")

        @app.get("/test-custom-app-error")
        def raise_custom():
            raise AppError(status_code=418, code="teapot", user_message="I'm a teapot")

        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    # ── 400: ModelNotAllowedError ──────────────────────────────────

    def test_model_not_allowed_returns_400_shape(self, client):
        """GIVEN a ModelNotAllowedError is raised
        WHEN the global handler processes it
        THEN 400 with error.code=model_not_allowed and error.detail.
        """
        response = client.get("/test-model-not-allowed")
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "model_not_allowed"
        assert "bad_model.safetensors" in body["error"]["detail"]

    # ── 500: ModelNotCachedError ───────────────────────────────────

    def test_model_not_cached_returns_500_shape(self, client):
        """GIVEN a ModelNotCachedError is raised
        WHEN the global handler processes it
        THEN 500 with error.code=model_not_cached and error.detail.
        """
        response = client.get("/test-model-not-cached")
        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "model_not_cached"
        assert "missing.safetensors" in body["error"]["detail"]

    # ── 422: UnsupportedWorkflowError ──────────────────────────────

    def test_unsupported_workflow_returns_422_shape(self, client):
        """GIVEN an UnsupportedWorkflowError is raised
        WHEN the global handler processes it
        THEN 422 with error.code=unsupported_workflow and error.detail.
        """
        response = client.get("/test-unsupported-workflow")
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "unsupported_workflow"
        assert "legacy" in body["error"]["detail"]

    # ── 403: SessionMismatchError ──────────────────────────────────

    def test_session_mismatch_returns_403_shape(self, client):
        """GIVEN a SessionMismatchError is raised
        WHEN the global handler processes it
        THEN 403 with error.code=session_mismatch and error.detail.
        """
        response = client.get("/test-session-mismatch")
        assert response.status_code == 403
        body = response.json()
        assert body["error"]["code"] == "session_mismatch"
        assert "req-session" in body["error"]["detail"]

    # ── Custom status code via AppError base ────────────────────────

    def test_custom_app_error_passes_status_code(self, client):
        """GIVEN an AppError with a custom status code
        WHEN the global handler processes it
        THEN the status code and error shape reflect the error fields.
        """
        response = client.get("/test-custom-app-error")
        assert response.status_code == 418
        body = response.json()
        assert body["error"]["code"] == "teapot"
        assert body["error"]["detail"] == "I'm a teapot"
