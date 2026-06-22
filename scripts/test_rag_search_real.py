import sys
from openai import OpenAI

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.ai.rag import CultureRagService


def main(query: str):
    db = SessionLocal()
    client = OpenAI(api_key=settings.openai_api_key)
    service = CultureRagService(client)

    embedding = service._embed(query)
    documents = service._search(db, embedding, query)

    print(f"\n=== Query: {query} ===")
    print(f"threshold={settings.rag_similarity_threshold} candidate_k={settings.rag_candidate_k} "
          f"vector_weight={settings.rag_vector_rank_weight} lexical_weight={settings.rag_lexical_rank_weight}")
    print(f"최종 context 문서 수: {len(documents)}\n")

    if not documents:
        print("결과 없음 (threshold/limit_context_documents에서 전부 걸러짐)")

    for rank, doc in enumerate(documents, 1):
        marker = " <-- 자수장" if "자수" in (doc.title or "") else ""
        print(f"{rank:2d}. id={doc.id:4d} title={doc.title} category={doc.category}{marker}")

    db.close()


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "자수장"
    main(query)
