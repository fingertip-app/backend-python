import json
import logging
from typing import Any

from openai import OpenAI, OpenAIError

from app.core.config import settings

logger = logging.getLogger(__name__)


class ReviewSummaryService:
    def __init__(self, client: OpenAI | None = None) -> None:
        if client is None:
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key is not configured")
            client = OpenAI(api_key=settings.openai_api_key)
        self.client = client

    def summarize(self, content: str, locale: str) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=settings.openai_generation_model,
            messages=[
                {
                    "role": "system",
                    "content": self._get_system_prompt(locale),
                },
                {
                    "role": "user",
                    "content": content,
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        response_text = response.choices[0].message.content
        if response_text is None:
            raise ValueError("Empty response from OpenAI")

        result = json.loads(response_text)
        return {
            "summary": result.get("summary", ""),
            "sentimentScore": float(result.get("sentimentScore", 0.5)),
            "keywords": result.get("keywords", []),
        }

    @staticmethod
    def _get_system_prompt(locale: str) -> str:
        locale_desc = "Korean" if locale == "ko" else "English"
        return f"""You are a helpful assistant that summarizes user reviews of cultural experiences.
Analyze the provided review and return a JSON object with the following fields:
- summary: A concise summary of the review (2-3 sentences in {locale_desc})
- sentimentScore: A decimal number between 0 and 1 indicating the sentiment (0=negative, 0.5=neutral, 1=positive)
- keywords: A list of 3-5 key topics or themes from the review

Respond only with valid JSON, no additional text."""
