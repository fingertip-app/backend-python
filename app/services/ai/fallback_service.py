import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class FallbackService:
    def __init__(self, data_path: str | None = None) -> None:
        self.data_path = data_path or settings.ai_fallback_data_path

    def get_fallback_response(self, query: str) -> dict[str, Any] | None:
        data = self._load_data()
        responses = data.get("responses", {})
        if not isinstance(responses, dict):
            logger.error("AI fallback data has invalid responses format")
            return None

        normalized_query = self._normalize(query)

        for key, response in responses.items():
            if normalized_query == self._normalize(key):
                return self._normalize_response(response)

        for key, response in responses.items():
            normalized_key = self._normalize(key)
            if normalized_key and (
                normalized_key in normalized_query or normalized_query in normalized_key
            ):
                return self._normalize_response(response)

        return None

    def _load_data(self) -> dict[str, Any]:
        path = Path(self.data_path)
        if not path.is_absolute():
            path = Path.cwd() / path

        try:
            with path.open(encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            logger.error("AI fallback data file does not exist: %s", path)
            return {}
        except json.JSONDecodeError:
            logger.exception("AI fallback data file is not valid JSON: %s", path)
            return {}

        if not isinstance(data, dict):
            logger.error("AI fallback data root must be a JSON object: %s", path)
            return {}
        return data

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.strip().lower().split())

    @staticmethod
    def _normalize_response(response: Any) -> dict[str, Any] | None:
        if not isinstance(response, dict):
            return None
        return {
            "answer": response.get("answer", ""),
            "sources": response.get("sources", []),
            "matchingKeywords": response.get("matchingKeywords", []),
            "recommendedCategories": response.get("recommendedCategories", []),
        }
