"""Prepare missing AI tables on the existing local Docker database only.

This is a local repair utility, not a production migration or Alembic stamp.
"""
from sqlalchemy import inspect, text

from app.db.models import EmbeddingMetadata, VectorDocument, ExperienceCultureLink
from app.db.session import engine


def main() -> None:
    url = engine.url
    if url.host not in {"localhost", "127.0.0.1"} or url.database != "janginharou":
        raise SystemExit("Refusing to modify anything except local janginharou")
    with engine.begin() as connection:
        inspector = inspect(connection)
        if not {"heritage_items", "experiences"}.issubset(inspector.get_table_names()):
            raise SystemExit("Prepare Spring base tables first")
        for table, column in (("heritage_items", "embedding"),
                              ("experiences", "description_embedding")):
            actual = connection.execute(text(
                "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
                "JOIN pg_class c ON c.oid=a.attrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relname=:table "
                "AND a.attname=:column AND NOT a.attisdropped"
            ), {"table": table, "column": column}).scalar()
            if actual != "vector(1536)":
                raise SystemExit(f"Unexpected vector type: {table}.{column}")
        for table in (VectorDocument.__table__, EmbeddingMetadata.__table__, ExperienceCultureLink.__table__):
            table.create(connection, checkfirst=True)
            actual_columns = {c["name"] for c in inspect(connection).get_columns(table.name)}
            if not set(table.columns.keys()).issubset(actual_columns):
                raise SystemExit(f"Existing {table.name} needs manual schema review")
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_experiences_description_embedding_hnsw "
            "ON experiences USING hnsw (description_embedding vector_cosine_ops)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_heritage_items_embedding_hnsw "
            "ON heritage_items USING hnsw (embedding vector_cosine_ops)"
        ))
    print("Local AI tables and vector indexes ready; Alembic history unchanged")


if __name__ == "__main__":
    main()
