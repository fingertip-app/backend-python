"""
충북 전용 AI 챗봇 서비스. DB(pgvector) 없이 동작한다.

app/services/ai/rag.py(CultureRagService)와 같은 역할이지만, 데이터 소스가
chungbuk_heritage.json(파일)이라는 점이 다르다. 데이터 건수가 적어(수십 건) DB·인덱스
없이 프로세스 메모리에 임베딩을 올려두고 매 요청마다 코사인 유사도를 계산해도 충분하다.
기존 CultureRagService와 데이터/코드가 완전히 분리되어 있어 서로 영향을 주지 않는다.
"""

import logging
import threading
from typing import Any

import numpy as np
from fastapi import HTTPException, status
from openai import OpenAI, OpenAIError

from app.core.config import settings
from app.schemas.ai import validate_explain_response
from app.services.ai.privacy import mask_personal_data
from app.services.chungbuk.data_store import read_json

logger = logging.getLogger(__name__)

HERITAGE_FILE = "chungbuk_heritage.json"

# 같은 프로세스 내에서 동시 요청이 임베딩 로드를 중복 실행하지 않도록 막는 락
_embedding_load_lock = threading.Lock()

CHUNGBUK_SYSTEM_INSTRUCTIONS = (
    "너는 충청북도 시도무형유산을 소개하는 AI 안내자야. "
    "반드시 아래에 주어진 충북 참고자료만 바탕으로 답변하고, 참고자료 밖의 내용은 추측하지 마. "
    "참고자료가 질문과 관련이 없으면 모른다고 답해."
)


class ChungbukRagService:
    # 헤리티지 청크 + 임베딩 캐시. 프로세스 시작 후 첫 요청에서 1회 계산되어 메모리에 유지된다.
    _embedded_chunks: list[dict[str, Any]] | None = None
    _embedding_matrix: np.ndarray | None = None

    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def explain(self, query: str, locale: str = "ko") -> dict[str, Any]:
        safe_query = mask_personal_data(query)
        self._ensure_embeddings_loaded()

        if not self._embedded_chunks:
            return validate_explain_response({
                "answer": "충북 무형유산 자료가 아직 준비되지 않았습니다.",
                "sources": [],
                "matchingKeywords": [],
                "recommendedCategories": [],
            })

        try:
            query_embedding = self._embed(safe_query)
        except OpenAIError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding provider request failed",
            ) from error

        top_chunks = self._search(query_embedding)
        if not top_chunks:
            return validate_explain_response({
                "answer": "관련 충북 무형유산 자료를 찾지 못했습니다. 질문을 더 구체적으로 입력해 주세요.",
                "sources": [],
                "matchingKeywords": [],
                "recommendedCategories": [],
            })

        context = "\n\n".join(
            f"[{chunk['name']} / {chunk['source']}]\n{chunk['content']}" for chunk in top_chunks
        )

        try:
            answer = self._generate_answer(context, safe_query, locale)
        except OpenAIError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Generation provider request failed",
            ) from error

        seen_ids = set()
        sources = []
        for chunk in top_chunks:
            if chunk["id"] not in seen_ids:
                seen_ids.add(chunk["id"])
                sources.append({
                    "id": chunk["id"],
                    "name": chunk["name"],
                    "source": chunk["source"],
                    "category": chunk.get("category"),
                })

        try:
            return validate_explain_response({
                "answer": answer,
                "sources": sources,
                "matchingKeywords": [],
                "recommendedCategories": list({c.get("category") for c in top_chunks if c.get("category")}),
            })
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Generation response schema validation failed",
            ) from error

    def _ensure_embeddings_loaded(self) -> None:
        cls = type(self)
        if cls._embedded_chunks is not None:
            return

        with _embedding_load_lock:
            # 락 대기 중 다른 요청이 먼저 로드를 끝냈는지 재확인 (같은 프로세스 내 중복 호출 방지)
            if cls._embedded_chunks is not None:
                return

            heritage_items = read_json(HERITAGE_FILE, default=[])
            chunks = []
            for item in heritage_items:
                content = "\n".join(
                    part for part in [item.get("description"), item.get("history")] if part
                )
                if not content:
                    continue
                chunks.append({
                    "id": item["id"],
                    "name": item.get("name", ""),
                    "category": item.get("category"),
                    "source": item.get("source", "충청북도 시도무형유산 현황"),
                    "content": content,
                })

            if not chunks:
                cls._embedded_chunks = []
                cls._embedding_matrix = np.empty((0, 0))
                return

            embeddings = self.client.embeddings.create(
                model=settings.openai_embedding_model,
                input=[chunk["content"] for chunk in chunks],
                encoding_format="float",
            )
            vectors = np.array([row.embedding for row in embeddings.data], dtype=np.float32)
            # 코사인 유사도를 내적으로 계산할 수 있도록 미리 정규화
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1
            cls._embedding_matrix = vectors / norms
            cls._embedded_chunks = chunks
            logger.info("Chungbuk heritage embeddings loaded: %d chunks", len(chunks))

    def _embed(self, query: str) -> np.ndarray:
        result = self.client.embeddings.create(
            model=settings.openai_embedding_model,
            input=query,
            encoding_format="float",
        )
        vector = np.array(result.data[0].embedding, dtype=np.float32)
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def _search(self, query_embedding: np.ndarray, top_k: int = 5) -> list[dict[str, Any]]:
        if self._embedding_matrix is None or self._embedding_matrix.size == 0:
            return []

        similarities = self._embedding_matrix @ query_embedding
        top_indices = np.argsort(-similarities)[:top_k]
        threshold = settings.rag_similarity_threshold
        return [
            self._embedded_chunks[i]
            for i in top_indices
            if similarities[i] >= threshold
        ]

    def _generate_answer(self, context: str, query: str, locale: str) -> str:
        response = self.client.responses.create(
            model=settings.openai_generation_model,
            instructions=CHUNGBUK_SYSTEM_INSTRUCTIONS,
            input=f"Locale: {locale}\nQuestion: {query}\n\n충북 참고자료:\n{context}",
        )
        return response.output_text or ""


def get_chungbuk_rag_service() -> ChungbukRagService:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API is not configured",
        )
    return ChungbukRagService(OpenAI(api_key=settings.openai_api_key))
