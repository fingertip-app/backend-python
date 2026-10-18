"""Local-only synthetic pottery fixtures and real embedding/generation smoke check.

No booking schedules or real artisan identities are created. Fixtures remain in
the local database for follow-up inspection. They are not research evidence.
"""
import argparse
import json
from types import SimpleNamespace

from openai import OpenAI
from sqlalchemy import text

from app.core.config import settings
from app.db.models import HeritageItem, VectorDocument
from app.db.session import SessionLocal, engine
from app.services.ai.experience_rag import ExperienceRagService
from app.services.ai.rag import CultureRagService


FIXTURES = (
    ("celadon", "[테스트] 청자 상감", "청자", "경기도 이천시", 25000,
     "[가상 검증 자료] 청자 상감 실습용 체험이다. 문양을 새기고 다른 색 흙으로 "
     "채우는 실습을 한다. 백자 채색 수업과 구분하기 위한 합성 데이터다."),
    ("white", "[테스트] 백자 채색", "백자", "경상남도 김해시", 45000,
     "[가상 검증 자료] 백자 그릇의 표면에 그림을 그리는 채색 체험이다. "
     "청자 상감이나 물레 성형을 가르치는 체험이 아니다."),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Use synthetic unit vectors; no LLM call")
    offline = parser.parse_args().offline
    if engine.url.host not in {"localhost", "127.0.0.1"} or engine.url.database != "janginharou":
        raise SystemExit("Local Docker janginharou database required")
    if not offline and not settings.openai_api_key:
        raise SystemExit("Model API key missing")
    client = None if offline else OpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=0)
    vectors = [SimpleNamespace(embedding=[float(j == i) for j in range(1536)])
               for i in range(len(FIXTURES))] if offline else client.embeddings.create(
        model=settings.openai_embedding_model,
        input=[f"{title} {description}" for _, title, _, _, _, description in FIXTURES],
    ).data
    with SessionLocal() as db:
        user_id = db.execute(text(
            "INSERT INTO users(email,provider,provider_id,nickname) "
            "VALUES ('pottery-smoke@example.invalid','local_test','pottery-smoke',"
            "'[테스트] 도자 검증') ON CONFLICT(email) DO UPDATE SET nickname=EXCLUDED.nickname "
            "RETURNING id"
        )).scalar_one()
        artisan_id = db.execute(text(
            "SELECT id FROM artisans WHERE user_id=:uid AND name='[테스트] 가상 도예가'"
        ), {"uid": user_id}).scalar()
        if artisan_id is None:
            artisan_id = db.execute(text(
                "INSERT INTO artisans(user_id,name,heritage_category,bio,is_verified) "
                "VALUES (:uid,'[테스트] 가상 도예가','도자기',"
                "'실존 인물이 아닌 로컬 검색 검증 데이터',false) RETURNING id"
            ), {"uid": user_id}).scalar_one()
        for fixture, vector in zip(FIXTURES, vectors):
            slug, title, category, address, price, description = fixture
            item = db.query(HeritageItem).filter_by(external_id=f"local-smoke-{slug}").first()
            if item is None:
                item = HeritageItem(external_id=f"local-smoke-{slug}")
                db.add(item)
            item.name, item.category = title, category
            item.source = "LOCAL_SYNTHETIC_FIXTURE"
            item.description, item.embedding = description, vector.embedding
            db.flush()
            document = db.query(VectorDocument).filter_by(heritage_item_id=item.id).first()
            if document is None:
                document = VectorDocument(heritage_item_id=item.id, chunk_index=0)
                db.add(document)
            document.content, document.embedding = description, vector.embedding
            document.title, document.category, document.source = title, category, item.source
            exp_id = db.execute(text(
                "SELECT id FROM experiences WHERE artisan_id=:aid AND title=:title"
            ), {"aid": artisan_id, "title": title}).scalar()
            if exp_id is None:
                exp_id = db.execute(text(
                    "INSERT INTO experiences(artisan_id,title,description,category,price,"
                    "duration_minutes,max_participants,location_address,is_active) "
                    "VALUES (:aid,:title,:description,:category,:price,60,4,:address,true) "
                    "RETURNING id"
                ), {"aid": artisan_id, "title": title, "description": description,
                    "category": category, "price": price, "address": address}).scalar_one()
            db.execute(text(
                "UPDATE experiences SET description_embedding=CAST(:embedding AS vector) WHERE id=:id"
            ), {"embedding": str(vector.embedding), "id": exp_id})
        db.commit()

    query = "청자 상감 기법을 직접 실습하고 싶어요"
    embedding = vectors[0].embedding if offline else client.embeddings.create(
        model=settings.openai_embedding_model, input=query
    ).data[0].embedding
    with SessionLocal() as db:
        culture = CultureRagService(client)
        documents = culture._search(db, embedding, query)
        experiences = ExperienceRagService(client)._search_experiences(db, embedding, 2)
        if not documents or documents[0].category != "청자":
            raise RuntimeError("Expected celadon culture document ranked first")
        if not experiences or experiences[0].category != "청자":
            raise RuntimeError("Expected celadon experience ranked first")
        response = None if offline else culture.explain(db, query, "ko")
        if response is not None and (not response["answer"].strip() or not response["sources"]):
            raise RuntimeError("Generation returned no answer or sources")
        print(json.dumps({
            "dataset": "LOCAL_SYNTHETIC_FIXTURE",
            "cultureTopCategory": documents[0].category,
            "experienceTopCategory": experiences[0].category,
            "embeddingMode": "synthetic_unit_vectors" if offline else "provider",
            "generatedAnswerNonempty": None if response is None else bool(response["answer"].strip()),
            "sourcesReturned": None if response is None else len(response["sources"]),
            "bookingSchedulesCreated": 0,
            "note": "Infrastructure smoke check only; not real-world quality evaluation",
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Provider/DB error messages can contain connection or request details.
        raise SystemExit(f"Local pottery smoke failed: {type(error).__name__}") from None
