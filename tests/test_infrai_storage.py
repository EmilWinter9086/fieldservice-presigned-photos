import httpx
import pytest
from fastapi.testclient import TestClient

from fieldservice_uploads.infrai_storage import InfraiError, InfraiStorage
from fieldservice_uploads.upload_service import build_app


def test_presign_places_bucket_and_key_in_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        route = "/v1/storage/object/presign/"
        assert request.url.path == route + "field-assets/" + "work-orders/42/photo.jpg"
        assert request.read().decode().find('"expires_seconds":600') >= 0
        return httpx.Response(200, json={"ok": True, "data": {"url": "https://upload.example/signed"}, "error": None, "metadata": {}})

    client = InfraiStorage(api_key="test-key", transport=httpx.MockTransport(handler))
    result = client.presign_put(
        "field-assets",
        "work-orders/42/photo.jpg",
        content_type="image/jpeg",
        max_bytes=1024,
        idempotency_key="request-42",
    )
    client.close()
    assert result["url"] == "https://upload.example/signed"


class FailingStorage:
    def __init__(self, code: str) -> None:
        self.code = code

    def create_bucket(self, _name: str) -> None:
        raise InfraiError(self.code, {"message": "setup failed"}, 409)


def test_startup_accepts_an_existing_bucket() -> None:
    with TestClient(build_app(storage=FailingStorage("STORAGE_BUCKET_EXISTS"))):
        pass


def test_startup_propagates_other_storage_errors() -> None:
    with pytest.raises(InfraiError), TestClient(build_app(storage=FailingStorage("OTHER_ERROR"))):
        pass
