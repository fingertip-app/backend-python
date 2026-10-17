from app.db.base import Base
from app.main import app


def test_fastapi_ai_schema_tables_defined():
    """AI 스키마와 Spring 소유 체험 테이블의 추천용 매핑을 등록한다"""
    tables = {table.name for table in Base.metadata.tables.values()}
    # experiences is mapped for recommendation reads; its base table is created by Spring.
    expected = {"heritage_items", "vector_documents", "embedding_metadata", "experiences"}
    assert tables == expected


def test_spring_owned_external_routes_are_not_exposed():
    paths = set(app.openapi()["paths"])

    assert "/api/v1/ai/explain" in paths
    assert "/api/v1/experiences" not in paths
    assert "/api/v1/bookings" not in paths
    assert "/api/v1/cardnews" not in paths
