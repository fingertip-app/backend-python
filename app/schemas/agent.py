"""Version-one wire contracts. These schemas do not expose an agent endpoint."""
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


class StrictContract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class RegionCode(StrEnum):
    SEOUL = 'SEOUL'
    GYEONGGI = 'GYEONGGI'
    INCHEON = 'INCHEON'
    BUSAN = 'BUSAN'
    JEJU = 'JEJU'


class AgentStatus(StrEnum):
    COMPLETED = 'completed'
    NO_MATCH = 'no_match'
    CLARIFICATION_REQUIRED = 'clarification_required'
    DEGRADED = 'degraded'


PriceKrw = Annotated[Decimal, Field(ge=0, decimal_places=2, allow_inf_nan=False)]
Text = Annotated[str, Field(min_length=1)]
QueryTerm = Annotated[str, Field(min_length=1, max_length=50)]


class AgentConstraints(StrictContract):
    regionCode: RegionCode | None = None
    maxPriceKrw: PriceKrw | None = None
    headCount: int = Field(default=1, ge=1, le=20, strict=True)

    @field_serializer('maxPriceKrw')
    def serialize_price(self, value: Decimal | None) -> str | None:
        return format(value, 'f') if value is not None else None


class AgentRequest(StrictContract):
    query: str = Field(min_length=1, max_length=500)
    locale: Literal['ko'] = 'ko'
    constraints: AgentConstraints = Field(default_factory=AgentConstraints)


class CatalogSearchRequest(StrictContract):
    queryTerms: list[QueryTerm] = Field(min_length=1, max_length=5)
    constraints: AgentConstraints = Field(default_factory=AgentConstraints)
    limit: int = Field(default=5, ge=1, le=10, strict=True)


class CatalogExperienceResponse(StrictContract):
    id: int = Field(gt=0, strict=True)
    title: Text
    descriptionExcerpt: str = Field(max_length=1200)
    tags: list[Text]
    priceKrw: PriceKrw
    maxParticipants: int = Field(ge=1, strict=True)
    regionCode: RegionCode | None
    isActive: bool = Field(strict=True)

    @field_serializer('priceKrw')
    def serialize_price(self, value: Decimal) -> str:
        return format(value, 'f')


class CatalogExperienceDetailsResponse(CatalogExperienceResponse):
    description: str


class CultureSearchRequest(StrictContract):
    query: str = Field(min_length=1, max_length=500)


class CultureDocument(StrictContract):
    documentId: Text
    heritageId: Text
    title: Text
    source: Text
    category: str | None
    contentExcerpt: str = Field(max_length=1200)


class CultureSearchResponse(StrictContract):
    documents: list[CultureDocument] = Field(max_length=5)


class AgentRecommendation(StrictContract):
    experienceId: int = Field(gt=0, strict=True)
    reason: Text
    evidenceKeys: list[Text] = Field(min_length=1)


class CultureClaim(StrictContract):
    text: Text
    documentIds: list[Text] = Field(min_length=1)


class AgentDraft(StrictContract):
    recommendations: list[AgentRecommendation] = Field(default_factory=list)
    cultureClaims: list[CultureClaim] = Field(default_factory=list)


class AgentResponse(StrictContract):
    status: AgentStatus
    answer: Text
    recommendedExperienceIds: list[Annotated[int, Field(gt=0, strict=True)]]
    recommendations: list[AgentRecommendation]
    sources: list[CultureDocument]
    appliedConstraints: AgentConstraints
    unsupportedConstraints: list[Text]
    limitations: list[Text]
    requestId: Text

    @model_validator(mode='after')
    def check_outcome(self) -> Self:
        ids = [item.experienceId for item in self.recommendations]
        if ids != self.recommendedExperienceIds or len(ids) != len(set(ids)):
            raise ValueError('Recommendation IDs must match unique recommendation entries')
        if self.status in {AgentStatus.NO_MATCH, AgentStatus.CLARIFICATION_REQUIRED} and ids:
            raise ValueError('No-match and clarification responses cannot recommend experiences')
        if self.unsupportedConstraints and self.status != AgentStatus.CLARIFICATION_REQUIRED:
            raise ValueError('Unsupported conditions require clarification')
        return self
