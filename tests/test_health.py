from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.main import app


class HealthyDb:
    def execute(self, statement):
        return None


class FailingDb:
    def execute(self, statement):
        raise RuntimeError("database unavailable")


def override_db(db):
    def _override_db():
        yield db

    return _override_db


def test_health() -> None:
    app.dependency_overrides[deps.get_db] = override_db(HealthyDb())
    client = TestClient(app)
    response = client.get("/health")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_health_degraded_when_db_fails() -> None:
    app.dependency_overrides[deps.get_db] = override_db(FailingDb())
    client = TestClient(app)
    response = client.get("/health")
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": "error"}
