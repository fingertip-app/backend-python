import os

from openai import OpenAI
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal

SIMILARITY_THRESHOLD = float(os.getenv("SMOKE_SIMILARITY_THRESHOLD", "0.30"))
DEFAULT_QUERIES = (
    "조선시대 궁중 자수에 대해 알려주세요",
    "한산모시짜기에 대해 알려주세요",
    "판소리 배우고 싶어요",
    "매듭 공예가 뭐예요",
    "도자기 만드는 전통 기술",
    "우주여행 로켓 발사",
)


def search(query: str, top_k: int = 5, category: str | None = None) -> list[dict[str, object]]:
    client = OpenAI(api_key=settings.openai_api_key or None)
    embedding = client.embeddings.create(
        model=os.getenv("OPENAI_EMBEDDING_MODEL", settings.openai_embedding_model),
        input=query,
    ).data[0].embedding

    filter_clause = "AND category = :category" if category else ""

    sql = text(f"""
        SELECT title, category, LEFT(content, 80) as snippet,
               1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM vector_documents
        WHERE embedding IS NOT NULL
        {filter_clause}
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
    """)

    params = {"embedding": str(embedding), "top_k": top_k}
    if category:
        params["category"] = category

    with SessionLocal() as db:
        rows = db.execute(sql, params).fetchall()

    filtered = [r for r in rows if r.similarity >= SIMILARITY_THRESHOLD]
    return [
        {
            "title": r.title,
            "category": r.category,
            "snippet": r.snippet,
            "similarity": float(r.similarity),
        }
        for r in filtered
    ]


def run() -> None:
    for query in DEFAULT_QUERIES:
        print(f"=== {query} ===")
        results = search(query)
        print_results(results)


def print_results(results: list[dict[str, object]]) -> None:
    if not results:
        print(f"  결과 없음 (임계값 {SIMILARITY_THRESHOLD:.2f} 미만)\n")
        return

    for result in results:
        print(
            f"[{result['similarity']:.3f}] {result['title']} ({result['category']})\n"
            f"  {result['snippet']}\n"
        )


if __name__ == "__main__":
    run()
