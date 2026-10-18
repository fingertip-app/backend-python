import pytest
from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.main import app
from tests.conftest import HealthyDb


class FailingDb:
    def execute(self, statement):
        raise RuntimeError("database unavailable")


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def healthy_client():
    app.dependency_overrides[deps.get_db] = lambda: HealthyDb()
    return TestClient(app)


@pytest.fixture
def failing_client():
    app.dependency_overrides[deps.get_db] = lambda: FailingDb()
    return TestClient(app)


def test_health(healthy_client, monkeypatch) -> None:
    monkeypatch.setattr("app.main.settings.openai_api_key", "")
    monkeypatch.setattr("app.main.settings.ai_fallback_enabled", False)

    response = healthy_client.get("/health")
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "checks": {
            "db": "ok",
            "ai": "missing_openai_api_key",
            "fallback": "disabled",
        },
    }


def test_health_degraded_when_db_fails(failing_client) -> None:
    response = failing_client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["db"] == "error"


def test_health_ok_when_db_and_ai_are_configured(healthy_client, monkeypatch) -> None:
    monkeypatch.setattr("app.main.settings.openai_api_key", "test-key")

    response = healthy_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"]["db"] == "ok"
    assert response.json()["checks"]["ai"] == "configured"


def test_health_reports_fallback_state(healthy_client, monkeypatch) -> None:
    monkeypatch.setattr("app.main.settings.ai_fallback_enabled", True)

    response = healthy_client.get("/health")

    assert response.json()["checks"]["fallback"] == "enabled"


def test_request_id_header_is_returned(healthy_client) -> None:
    response = healthy_client.get("/health", headers={"X-Request-Id": "req-test-1"})

    assert response.headers["X-Request-Id"] == "req-test-1"
