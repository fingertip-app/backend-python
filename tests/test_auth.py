from collections.abc import Generator

from fastapi.testclient import TestClient
import pytest

from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.db.models import User
from app.db.session import get_db
from app.main import app


class FakeSession:
    def __init__(self) -> None:
        self.user: User | None = None
        self.next_id = 1

    def scalar(self, _statement: object) -> User | None:
        return self.user

    def add(self, user: User) -> None:
        if user.id is None:
            user.id = self.next_id
            self.next_id += 1
        self.user = user

    def commit(self) -> None:
        pass

    def refresh(self, user: User) -> None:
        if user.id is None:
            user.id = self.next_id
            self.next_id += 1

    def get(self, _model: type[User], user_id: int) -> User | None:
        if self.user is None or self.user.id != user_id:
            return None
        return self.user


def override_db(fake_db: FakeSession) -> None:
    def _get_db() -> Generator[FakeSession, None, None]:
        yield fake_db

    app.dependency_overrides[get_db] = _get_db


def teardown_function() -> None:
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def use_test_jwt_secret() -> Generator[None, None, None]:
    original_secret = settings.jwt_secret
    settings.jwt_secret = "test-secret-with-at-least-32-bytes"
    try:
        yield
    finally:
        settings.jwt_secret = original_secret


def test_dev_login_returns_token_and_current_user() -> None:
    fake_db = FakeSession()
    override_db(fake_db)
    client = TestClient(app)

    login_response = client.post(
        "/api/v1/auth/dev-login",
        json={"email": "yj@example.com", "nickname": "영진", "provider": "dev"},
    )

    assert login_response.status_code == 200
    payload = login_response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["user"]["email"] == "yj@example.com"

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["nickname"] == "영진"


def test_me_requires_token() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_me_rejects_inactive_user() -> None:
    inactive_user = User(
        id=10,
        email="inactive@example.com",
        provider="dev",
        nickname="inactive",
        is_active=False,
    )

    def _get_current_user() -> User:
        return inactive_user

    app.dependency_overrides[get_current_user] = _get_current_user
    client = TestClient(app)

    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer ignored"})

    assert response.status_code == 403
