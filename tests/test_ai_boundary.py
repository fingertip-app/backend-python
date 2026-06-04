from app.db.base import Base
from app.main import app


def test_fastapi_ai_schema_tables_defined():
    """FastAPI는 AI 기능용 3개 테이블을 소유한다"""
    tables = {table.name for table in Base.metadata.tables.values()}
    expected = {"heritage_items", "vector_documents", "embedding_metadata"}
    assert tables == expected


def test_spring_owned_external_routes_are_not_exposed():
    paths = set(app.openapi()["paths"])

    assert "/api/v1/ai/explain" in paths
    assert "/api/v1/experiences" not in paths
    assert "/api/v1/bookings" not in paths
    assert "/api/v1/cardnews" not in paths
