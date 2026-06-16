import json
import logging
from typing import Any

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

MIN_SUMMARY_CONTENT_LENGTH = 10
DEFAULT_SENTIMENT_SCORE = 0.5
MAX_KEYWORDS = 5


class ReviewSummaryService:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.client = client

    def summarize(self, content: str, locale: str) -> dict[str, Any]:
        normalized_content = content.strip()
        if len(normalized_content) < MIN_SUMMARY_CONTENT_LENGTH:
            return self._short_review_response(normalized_content, locale)

        response = self._client().chat.completions.create(
            model=settings.openai_generation_model,
            messages=[
                {
                    "role": "system",
                    "content": self._get_system_prompt(locale),
                },
                {
                    "role": "user",
                    "content": normalized_content,
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        response_text = response.choices[0].message.content
        if response_text is None:
            raise ValueError("Empty response from OpenAI")

        result = json.loads(response_text)
        return self._normalize_result(result)

    def _client(self) -> OpenAI:
        if self.client is None:
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key is not configured")
            self.client = OpenAI(api_key=settings.openai_api_key)
        return self.client

    @staticmethod
    def _short_review_response(content: str, locale: str) -> dict[str, Any]:
        if locale == "en":
            summary = "The review is too short to summarize separately."
        elif content:
            summary = content
        else:
            summary = "후기 내용이 짧아 별도 요약을 생성하지 않았습니다."

        return {
            "summary": summary,
            "sentimentScore": DEFAULT_SENTIMENT_SCORE,
            "keywords": [],
        }

    @staticmethod
    def _normalize_result(result: dict[str, Any]) -> dict[str, Any]:
        raw_keywords = result.get("keywords", [])
        if not isinstance(raw_keywords, list):
            raw_keywords = []

        keywords = [
            str(keyword).strip()
            for keyword in raw_keywords
            if str(keyword).strip()
        ][:MAX_KEYWORDS]

        return {
            "summary": str(result.get("summary", "")).strip(),
            "sentimentScore": ReviewSummaryService._normalize_sentiment_score(
                result.get("sentimentScore", DEFAULT_SENTIMENT_SCORE)
            ),
            "keywords": keywords,
        }

    @staticmethod
    def _normalize_sentiment_score(value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return DEFAULT_SENTIMENT_SCORE
        return max(0.0, min(1.0, score))

    @staticmethod
    def _get_system_prompt(locale: str) -> str:
        locale_desc = "Korean" if locale == "ko" else "English"
        return f"""You are a helpful assistant that summarizes user reviews of cultural experiences.
Analyze the provided review and return a JSON object with the following fields:
- summary: A concise summary of the review (2-3 sentences in {locale_desc})
- sentimentScore: A decimal number between 0 and 1 indicating the sentiment (0=negative, 0.5=neutral, 1=positive)
- keywords: A list of 3-5 key topics or themes from the review

Respond only with valid JSON, no additional text."""
