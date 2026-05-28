from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.main import app
from tests.conftest import HealthyDb


class FailingDb:
    def execute(self, statement):
        raise RuntimeError("database unavailable")


def override_db(db):
    def _override_db():
        yield db

    return _override_db


def test_health() -> None:
    app.dependency_overrides[deps.get_db] = override_db(HealthyDb())
    try:
        response = TestClient(app).get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "db": "ok"}
    finally:
        app.dependency_overrides.clear()


def test_health_degraded_when_db_fails() -> None:
    app.dependency_overrides[deps.get_db] = override_db(FailingDb())
    try:
        response = TestClient(app).get("/health")
        assert response.status_code == 503
        assert response.json() == {"status": "degraded", "db": "error"}
    finally:
        app.dependency_overrides.clear()
