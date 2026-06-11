# smoke_test.py 임시 스크립트
import os
from openai import OpenAI
from sqlalchemy import text
from app.db.session import SessionLocal

client = OpenAI()
db = SessionLocal()

def search(query: str, top_k: int = 5, category: str = None):
    embedding = client.embeddings.create(
        model="text-embedding-3-small",
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

    rows = db.execute(sql, params).fetchall()
    for r in rows:
        print(f"[{r.similarity:.3f}] {r.title} ({r.category})\n  {r.snippet}\n")

# 테스트 케이스
print("=== 도자기 ===")
search("도자기 만들기 체험")

print("=== 존재하지 않는 키워드 ===")
search("우주여행 로켓 발사")

db.close()