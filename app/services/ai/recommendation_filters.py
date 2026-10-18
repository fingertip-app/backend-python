"""Explicit request conditions applied in SQL before vector top-k selection."""
import re

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select

from app.db.models import Experience, ExperienceCultureLink


REGION_ALIASES = (
    ("서울", "서울특별시"), ("부산", "부산광역시"), ("대구", "대구광역시"),
    ("인천", "인천광역시"), ("광주", "광주광역시"), ("대전", "대전광역시"),
    ("울산", "울산광역시"), ("세종", "세종특별자치시"), ("경기", "경기도"),
    ("강원", "강원도", "강원특별자치도"), ("충북", "충청북도"),
    ("충남", "충청남도"), ("전북", "전라북도", "전북특별자치도"),
    ("전남", "전라남도"), ("경북", "경상북도"), ("경남", "경상남도"),
    ("제주", "제주도", "제주특별자치도"),
)


def extract_region_candidates(query: str) -> set[str]:
    regions = set()
    for group in REGION_ALIASES:
        for alias in group:
            pattern = r"(?<![가-힣])" + alias + r"(?:에서| 지역| 근처)"
            if re.search(pattern, query):
                regions.add(group[0])
    return regions


class RecommendationFilters(BaseModel):
    region: str | None = Field(default=None, max_length=50)
    maxPrice: int | None = Field(default=None, ge=0)
    maxDurationMinutes: int | None = Field(default=None, ge=1)
    headCount: int | None = Field(default=None, ge=1, le=100)
    technique: str | None = Field(default=None, min_length=1, max_length=100)
    heritageItemId: int | None = Field(default=None, ge=1)

    @classmethod
    def resolve(cls, query: str, **explicit):
        """Conservative Korean patterns; explicit form fields take precedence.

        This is deliberately not a general natural-language parser. Multi-region
        requests and total-party budgets are left for clarification, not guessed.
        """
        inferred = {}
        regions = extract_region_candidates(query)
        if len(regions) == 1:
            inferred["region"] = regions.pop()
        if "총" not in query and "전체" not in query:
            prices = []
            for match in re.finditer(
                r"(?<![-\d.,])([0-9]+(?:,[0-9]{3})*)\s*(만)?\s*원\s*(이하|미만)", query
            ):
                amount = int(match[1].replace(",", "")) * (10000 if match[2] else 1)
                maximum = amount - (1 if match[3] == "미만" else 0)
                if maximum >= 0:
                    prices.append(maximum)
            if prices:
                inferred["maxPrice"] = min(prices)
        return cls(**{**inferred, **{key: value for key, value in explicit.items() if value is not None}})

    @field_validator("region")
    @classmethod
    def normalize_region(cls, value: str | None) -> str | None:
        value = " ".join(value.split()) if value else None
        if value in {None, "", "전국"}:
            return None
        if not re.fullmatch(r"[가-힣]+(?: [가-힣]+){0,2}", value):
            raise ValueError("지역은 시도·시군구 이름으로 입력해 주세요")
        return value

    def apply(self, statement):
        if self.region:
            parts = self.region.split()
            variants = next((group for group in REGION_ALIASES if parts[0] in group), None)
            if variants:
                # Province aliases must match the first address token. 광주 and
                # 경기도 광주시 must not be conflated by substring matching.
                patterns = ["^" + alias + r"([[:space:]]|$)" for alias in variants]
                statement = statement.where(or_(
                    *(Experience.location_address.op("~")(p) for p in patterns)
                ))
                parts = parts[1:]
            for token in parts:
                pattern = r"(^|[[:space:]])" + re.escape(token) + r"([[:space:]]|$)"
                statement = statement.where(Experience.location_address.op("~")(pattern))
        if self.maxPrice is not None:
            statement = statement.where(Experience.price <= self.maxPrice)
        if self.maxDurationMinutes is not None:
            statement = statement.where(Experience.duration_minutes <= self.maxDurationMinutes)
        if self.headCount is not None:
            statement = statement.where(Experience.max_participants >= self.headCount)
        if self.technique is not None or self.heritageItemId is not None:
            link = (select(ExperienceCultureLink.id)
                    .where(ExperienceCultureLink.experience_id == Experience.id)
                    .where(ExperienceCultureLink.review_status == "verified")
                    .where(ExperienceCultureLink.relation_kind == "direct_practice"))
            if self.technique is not None:
                link = link.where(ExperienceCultureLink.technique == self.technique)
            if self.heritageItemId is not None:
                link = link.where(ExperienceCultureLink.heritage_item_id == self.heritageItemId)
            statement = statement.where(link.exists())
        return statement
