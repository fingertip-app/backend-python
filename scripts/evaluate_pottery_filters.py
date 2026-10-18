"""Read local fixture vectors; roll back temporary relationship evidence.

Tests hard conditions against PostgreSQL, not semantic or real-world quality.
"""
import json
from datetime import datetime

from sqlalchemy import select

from app.core.config import settings
from app.db.models import Experience, ExperienceCultureLink, HeritageItem
from app.db.session import SessionLocal, engine
from app.services.ai.experience_rag import ExperienceRagService
from app.services.ai.recommendation_filters import RecommendationFilters


def main():
    if engine.url.host not in {"localhost", "127.0.0.1"} or engine.url.database != "janginharou":
        raise SystemExit("Local Docker database required")
    results = []
    with SessionLocal() as db:
        celadon = db.scalar(select(Experience).where(Experience.title == "[테스트] 청자 상감"))
        white = db.scalar(select(Experience).where(Experience.title == "[테스트] 백자 채색"))
        if celadon is None or white is None:
            raise SystemExit("Run pottery_local_smoke first")
        heritage = db.scalar(select(HeritageItem).where(HeritageItem.external_id == "local-smoke-celadon"))
        link = ExperienceCultureLink(
            experience_id=celadon.id, heritage_item_id=heritage.id, technique="상감",
            relation_kind="direct_practice", evidence_url="local://synthetic-fixture",
            evidence_excerpt="실제 장인 관계가 아닌 테스트용 연결 근거",
            review_status="pending", checked_at=datetime.now(),
        )
        db.add(link)
        db.flush()
        # Remove semantic threshold as a confounder for hard-filter evaluation.
        original_threshold = settings.rag_similarity_threshold
        settings.rag_similarity_threshold = -1.0
        service = ExperienceRagService(None)

        def check(name, filters, expected):
            found = service._search_experiences(db, list(celadon.description_embedding), 100, filters)
            ids = {exp.id for exp in found if exp.id in {celadon.id, white.id}}
            if ids != expected:
                raise AssertionError(f"Filter check failed: {name}")
            results.append({"case": name, "passed": True})

        try:
            check("baseline", RecommendationFilters(), {celadon.id, white.id})
            check("province_alias", RecommendationFilters(region="경기"), {celadon.id})
            check("province_and_city", RecommendationFilters(region="경기도 이천시"), {celadon.id})
            check("gimhae", RecommendationFilters(region="경남 김해시"), {white.id})
            original_address = white.location_address
            white.location_address = "경기도 광주시"
            db.flush()
            check("gwangju_metro_is_not_gyeonggi_city", RecommendationFilters(region="광주"), set())
            check("gyeonggi_gwangju_city", RecommendationFilters(region="경기 광주시"), {white.id})
            white.location_address = original_address
            db.flush()
            check("no_region_match", RecommendationFilters(region="서울"), set())
            check("price_boundary", RecommendationFilters(maxPrice=25000), {celadon.id})
            check("no_free_experience", RecommendationFilters(maxPrice=0), set())
            check("duration_excluded", RecommendationFilters(maxDurationMinutes=59), set())
            check("capacity_excluded", RecommendationFilters(headCount=5), set())
            check("combined", RecommendationFilters(region="경기", maxPrice=30000, headCount=4), {celadon.id})
            check("pending_link_excluded", RecommendationFilters(technique="상감"), set())
            link.review_status = "verified"
            db.flush()
            check("verified_direct_link", RecommendationFilters(technique="상감"), {celadon.id})
            link.relation_kind = "cultural_relation"
            db.flush()
            check("related_is_not_practice", RecommendationFilters(technique="상감"), set())
        finally:
            settings.rag_similarity_threshold = original_threshold
            db.rollback()
    print(json.dumps({"dataset": "synthetic", "semanticQualityMeasured": False,
                      "checks": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
