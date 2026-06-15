import warnings

from starlette.exceptions import StarletteDeprecationWarning


class LazyTestClient:
    def __init__(self, app):
        self._app = app
        self._client = None

    def _get_client(self):
        if self._client is None:
            warnings.filterwarnings("ignore", category=StarletteDeprecationWarning)
            from fastapi.testclient import TestClient

            self._client = TestClient(self._app)
        return self._client

    def __getattr__(self, name):
        return getattr(self._get_client(), name)

    def __enter__(self):
        return self._get_client().__enter__()

    def __exit__(self, exc_type, exc, tb):
        return self._get_client().__exit__(exc_type, exc, tb)
