from app.db.base import Base
from app.main import app


def test_fastapi_ai_schema_tables_defined():
    """AI 테이블과 기존 체험 추천용 조회 모델만 등록한다."""
    tables = {table.name for table in Base.metadata.tables.values()}
    expected = {"heritage_items", "vector_documents", "embedding_metadata", "experiences"}
    assert tables == expected


def test_spring_owned_external_routes_are_not_exposed():
    paths = set(app.openapi()["paths"])

    assert "/api/v1/ai/explain" in paths
    assert "/api/v1/experiences" not in paths
    assert "/api/v1/bookings" not in paths
    assert "/api/v1/cardnews" not in paths
