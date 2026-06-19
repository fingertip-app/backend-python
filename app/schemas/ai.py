from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class SourceResponse(BaseModel):
    id: int
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    category: str | None = None


class ExplainResponse(BaseModel):
    answer: str = Field(min_length=1)
    sources: list[SourceResponse]
    matchingKeywords: list[str]
    recommendedCategories: list[str]


class ReviewSummaryResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=1)
    sentimentScore: float = Field(ge=0.0, le=1.0)
    keywords: list[str] = Field(max_length=5)

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        if not value:
            raise ValueError("summary must not be empty")
        return value

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: list[str]) -> list[str]:
        return [keyword.strip() for keyword in value if keyword.strip()]


def validate_explain_response(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return ExplainResponse.model_validate(payload).model_dump()
    except ValidationError as error:
        raise ValueError("Invalid explain response schema") from error


def validate_review_summary_response(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return ReviewSummaryResponse.model_validate(payload).model_dump()
    except ValidationError as error:
        raise ValueError("Invalid review summary response schema") from error
