"""Version-one wire contracts. These schemas do not expose an agent endpoint."""
import json
import re
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import (AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, ValidationError,
                      WithJsonSchema, field_serializer, model_validator)


def parse_contract_json(raw: str | bytes | bytearray) -> Any:
    """Read a raw request body without routing decimal numeric tokens through float.

    Future HTTP routes must use this entry point on raw body bytes before model validation;
    FastAPI's default JSON parser has already lost this precision by the model boundary.
    """
    def reject_constant(value: str) -> None:
        raise ValueError(f'Non-finite JSON number: {value}')

    return json.loads(raw, parse_float=Decimal, parse_constant=reject_constant)


class StrictContract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    @classmethod
    def model_validate_json(
        cls, json_data: str | bytes | bytearray, *, strict: bool | None = None,
        extra: str | None = None, context: Any = None,
        by_alias: bool | None = None, by_name: bool | None = None,
    ) -> Self:
        try:
            value = parse_contract_json(json_data)
        except (ValueError, UnicodeDecodeError) as error:
            raise ValidationError.from_exception_data(cls.__name__, [{
                'type': 'json_invalid', 'loc': (), 'input': json_data,
                'ctx': {'error': str(error)},
            }]) from error
        options: dict[str, Any] = {'strict': strict, 'context': context,
                                  'by_alias': by_alias, 'by_name': by_name}
        if extra is not None:
            options['extra'] = extra
        return cls.model_validate(value, **options)


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


# Strings use ordinary unsigned decimal notation; trailing fractional zeros do not
# add monetary precision. Exponent notation is accepted only as a JSON number.
PRICE_STRING_PATTERN = r'^[0-9]+(?:\.[0-9]{1,2}0*)?$'


def validate_price_form(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError('A price must be a decimal number or string')
    if isinstance(value, str) and not re.fullmatch(PRICE_STRING_PATTERN, value):
        raise ValueError('Price string must use unsigned decimal notation with cent precision')
    return value


def normalize_price_zero(value: Decimal) -> Decimal:
    return value.copy_abs() if value.is_zero() else value


PriceKrw = Annotated[
    Decimal, BeforeValidator(validate_price_form),
    Field(ge=0, decimal_places=2, allow_inf_nan=False), AfterValidator(normalize_price_zero),
    WithJsonSchema({'anyOf': [
        {'type': 'number', 'minimum': 0, 'multipleOf': 0.01},
        {'type': 'string', 'pattern': PRICE_STRING_PATTERN},
    ]}, mode='validation'),
    WithJsonSchema({'type': 'string', 'pattern': PRICE_STRING_PATTERN}, mode='serialization'),
]
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
