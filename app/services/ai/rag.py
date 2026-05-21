def generate_culture_explanation(query: str, locale: str = "ko") -> dict[str, object]:
    # TODO(영진): OpenAI + pgvector 기반 RAG 구현.
    # TODO(서영): heritage/vector_documents 스키마와 검색 쿼리 연결.
    return {"answer": query, "locale": locale, "sources": []}
