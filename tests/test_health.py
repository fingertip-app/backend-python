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


def test_health(healthy_client) -> None:
    response = healthy_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_health_degraded_when_db_fails(failing_client) -> None:
    response = failing_client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": "error"}
