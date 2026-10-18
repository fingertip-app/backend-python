"""Real model + in-process HTTP API check against synthetic local fixtures."""
import json
from time import perf_counter

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.db.models import Experience
from app.db.session import SessionLocal, engine
from app.main import app


def main():
    if engine.url.host not in {"localhost", "127.0.0.1"} or engine.url.database != "janginharou":
        raise SystemExit("Local Docker database required")
    with SessionLocal() as db:
        expected = db.scalar(select(Experience.id).where(Experience.title == "[테스트] 청자 상감"))
    started = perf_counter()
    result = TestClient(app).post("/api/v1/ai/recommendations", headers={
        "X-Internal-Api-Key": settings.internal_api_key,
    }, json={"freeText": "경기에서 3만 원 이하 청자 상감 체험을 찾고 있어요",
             "headCount": 2, "maxDurationMinutes": 90})
    if result.status_code != 200:
        raise SystemExit(f"HTTP check failed: {result.status_code}")
    payload = result.json()
    assert payload["fallback"] is False
    assert payload["recommendedExperienceIds"] == [expected]
    assert payload["appliedFilters"]["region"] == "경기"
    assert payload["appliedFilters"]["maxPrice"] == 30000
    assert payload["answer"].strip()
    print(json.dumps({"dataset": "synthetic", "httpStatus": result.status_code,
                      "hardFiltersApplied": payload["appliedFilters"],
                      "matchingExperienceCount": len(payload["recommendedExperienceIds"]),
                      "generatedAnswerNonempty": True,
                      "elapsedSeconds": round(perf_counter() - started, 2),
                      "realArtisanQualityMeasured": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"API smoke failed: {type(error).__name__}") from None
