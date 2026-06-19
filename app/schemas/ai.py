from typing import Any

from pydantic import BaseModel, Field, ValidationError


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


def validate_explain_response(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return ExplainResponse.model_validate(payload).model_dump()
    except ValidationError as error:
        raise ValueError("Invalid explain response schema") from error
