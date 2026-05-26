from app.db.base import Base
from app.main import app


def test_fastapi_owns_only_heritage_item_table():
    assert set(Base.metadata.tables) == {"heritage_items"}


def test_spring_owned_external_routes_are_not_exposed():
    paths = set(app.openapi()["paths"])

    assert "/api/v1/ai/explain" in paths
    assert "/api/v1/experiences" not in paths
    assert "/api/v1/bookings" not in paths
    assert "/api/v1/cardnews" not in paths
