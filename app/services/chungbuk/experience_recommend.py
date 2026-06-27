"""
충북 체험 추천 서비스. DB 없이 chungbuk_experiences.json을 메모리에 올려 동작한다.

기획서의 "충북 우선 노출 정책"을 랭킹 단계에 반영한다: 임베딩 유사도가 SIMILARITY_BAND
안에서 동일한 구간으로 묶이면, 그 구간 안에서는 region=충북 체험을 먼저 노출한다.
지금은 풀 전체가 충북 데이터라 이 정책이 항상 참(no-op)이지만, 나중에 타지역 체험이
같은 풀에 섞여도 정책이 그대로 작동하도록 region 비교로 구현했다.
"""

import logging
import threading
from typing import Any

import numpy as np
from fastapi import HTTPException, status
from openai import OpenAI, OpenAIError

from app.core.config import settings
from app.services.chungbuk.data_store import read_json

logger = logging.getLogger(__name__)

EXPERIENCES_FILE = "chungbuk_experiences.json"

# 이 폭 안에 들어오는 유사도는 "동일 구간"으로 보고 region 가중치로 순서를 정한다.
SIMILARITY_BAND = 0.03
PRIORITY_REGION = "충북"

_load_lock = threading.Lock()


class ChungbukExperienceRecommendService:
    _experiences: list[dict[str, Any]] | None = None
    _embedding_matrix: np.ndarray | None = None

    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def recommend(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        self._ensure_loaded()
        if not self._experiences:
            return []

        try:
            query_embedding = self._embed(query)
        except OpenAIError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding provider request failed",
            ) from error

        similarities = self._embedding_matrix @ query_embedding
        ranked_indices = self._rank_with_region_weight(similarities)
        return [
            {**self._experiences[i], "similarity": float(similarities[i])}
            for i in ranked_indices[:top_k]
        ]

    def _rank_with_region_weight(self, similarities: np.ndarray) -> list[int]:
        """
        '동일 유사도 구간일 경우 region=충북 우선 노출' 정책 — 가중치 한 줄(REGION_BONUS).

        두 항목의 유사도 차이가 SIMILARITY_BAND 이내(=동일 구간)면 충북 가중치가 그 차이를
        뒤집을 만큼 커서 충북 항목이 앞에 오고, 차이가 SIMILARITY_BAND를 넘으면 가중치보다
        유사도 차이가 더 크므로 원래 유사도 순서가 그대로 유지된다.
        고정 구간으로 나누는 방식(버킷팅)은 경계값에서 가까운 두 점이 다른 버킷으로
        갈리는 문제가 있어, 점수에 가중치를 더하는 방식으로 구현했다.
        """
        experiences = self._experiences

        def combined_score(i: int) -> float:
            region_bonus = SIMILARITY_BAND if experiences[i].get("region") == PRIORITY_REGION else 0.0
            return float(similarities[i]) + region_bonus

        return sorted(
            range(len(similarities)),
            key=lambda i: (combined_score(i), float(similarities[i])),
            reverse=True,
        )

    def _ensure_loaded(self) -> None:
        cls = type(self)
        if cls._experiences is not None:
            return

        with _load_lock:
            if cls._experiences is not None:
                return

            experiences = read_json(EXPERIENCES_FILE, default=[])
            if not experiences:
                cls._experiences = []
                cls._embedding_matrix = np.empty((0, 0))
                return

            texts = [f"{e.get('title', '')} {e.get('description', '')}" for e in experiences]
            embeddings = self.client.embeddings.create(
                model=settings.openai_embedding_model,
                input=texts,
                encoding_format="float",
            )
            vectors = np.array([row.embedding for row in embeddings.data], dtype=np.float32)
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1
            cls._embedding_matrix = vectors / norms
            cls._experiences = experiences
            logger.info("Chungbuk experience embeddings loaded: %d items", len(experiences))

    def _embed(self, query: str) -> np.ndarray:
        result = self.client.embeddings.create(
            model=settings.openai_embedding_model,
            input=query,
            encoding_format="float",
        )
        vector = np.array(result.data[0].embedding, dtype=np.float32)
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector


def get_chungbuk_experience_recommend_service() -> ChungbukExperienceRecommendService:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API is not configured",
        )
    return ChungbukExperienceRecommendService(OpenAI(api_key=settings.openai_api_key))
