"""
기존 Experience 데이터의 description을 임베딩하여 description_embedding 컬럼에 저장하는 스크립트

실행 방법:
    uv run python scripts/generate_experience_embeddings.py
"""
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from openai import OpenAI
from sqlalchemy import select

from app.core.config import settings
from app.db.models import Experience
from app.db.session import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_embeddings():
    """모든 활성화된 Experience의 description을 임베딩으로 변환"""
    db = SessionLocal()
    client = OpenAI(api_key=settings.openai_api_key)

    try:
        # description_embedding이 NULL인 활성화된 체험 조회
        stmt = select(Experience).where(
            Experience.is_active.is_(True),
            Experience.description_embedding.is_(None)
        )
        experiences = db.execute(stmt).scalars().all()

        if not experiences:
            logger.info("✅ 임베딩이 필요한 체험이 없습니다.")
            return

        logger.info(f"📊 총 {len(experiences)}개 체험의 임베딩을 생성합니다.")

        success_count = 0
        error_count = 0

        for idx, exp in enumerate(experiences, 1):
            try:
                # description을 임베딩
                logger.info(f"[{idx}/{len(experiences)}] 체험 ID {exp.id}: {exp.title[:30]}...")

                # 임베딩할 텍스트 구성 (제목 + 설명 + 문화 이야기)
                embedding_text = f"{exp.title}\n{exp.description}"
                if exp.cultural_story:
                    embedding_text += f"\n{exp.cultural_story}"

                response = client.embeddings.create(
                    model=settings.openai_embedding_model,
                    input=embedding_text,
                    encoding_format="float",
                )

                embedding = response.data[0].embedding

                # DB 업데이트
                exp.description_embedding = embedding
                db.commit()

                success_count += 1
                logger.info(f"  ✅ 임베딩 저장 완료")

            except Exception as error:
                error_count += 1
                logger.error(f"  ❌ 임베딩 생성 실패: {error}")
                db.rollback()
                continue

        logger.info(f"\n{'='*60}")
        logger.info(f"✅ 완료: {success_count}개 성공, ❌ {error_count}개 실패")
        logger.info(f"{'='*60}")

    except Exception as error:
        logger.exception(f"스크립트 실행 중 오류 발생: {error}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    generate_embeddings()
