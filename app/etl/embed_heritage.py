"""
국가무형유산 임베딩 배치 생성 스크립트

사용법:
    python -m app.etl.embed_heritage           # 전체 PENDING 처리
    python -m app.etl.embed_heritage --retry-failed  # FAILED 재처리
"""

import argparse
import time
from datetime import datetime, timezone

from openai import OpenAI
from sqlalchemy.orm import Session

from app.db.models import EmbeddingMetadata, EmbeddingStatus, HeritageItem, VectorDocument
from app.db.session import SessionLocal

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
DELAY = 0.5  # OpenAI API 과호출 방지


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """텍스트를 chunk_size 단위로 분할. overlap만큼 앞 내용 포함."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap

    return chunks


def get_embedding(client: OpenAI, text: str) -> list[float]:
    """단일 텍스트 임베딩 생성."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def get_pending_items(db: Session, retry_failed: bool) -> list[HeritageItem]:
    """처리 대상 HeritageItem 조회.

    retry_failed=True면 FAILED 항목도 포함.
    이미 DONE인 항목은 제외.
    """
    done_ids = (
        db.query(EmbeddingMetadata.target_id)
        .filter(
            EmbeddingMetadata.target_table == "heritage_items",
            EmbeddingMetadata.status == EmbeddingStatus.DONE.value,
        )
        .subquery()
    )

    query = db.query(HeritageItem).filter(HeritageItem.id.notin_(done_ids))

    if not retry_failed:
        failed_ids = (
            db.query(EmbeddingMetadata.target_id)
            .filter(
                EmbeddingMetadata.target_table == "heritage_items",
                EmbeddingMetadata.status == EmbeddingStatus.FAILED.value,
            )
            .subquery()
        )
        query = query.filter(HeritageItem.id.notin_(failed_ids))

    return query.all()


def upsert_metadata(db: Session, item_id: int, status: EmbeddingStatus, error: str | None = None) -> None:
    """EmbeddingMetadata 상태 upsert."""
    meta = (
        db.query(EmbeddingMetadata)
        .filter_by(target_table="heritage_items", target_id=item_id)
        .first()
    )
    now = datetime.now(timezone.utc)

    if meta is None:
        meta = EmbeddingMetadata(
            target_table="heritage_items",
            target_id=item_id,
            status=status.value,
            error_message=error,
            embedded_at=now if status == EmbeddingStatus.DONE else None,
            created_at=now,
        )
        db.add(meta)
    else:
        meta.status = status.value
        meta.error_message = error
        meta.embedded_at = now if status == EmbeddingStatus.DONE else meta.embedded_at


def process_item(client: OpenAI, db: Session, item: HeritageItem) -> None:
    """단일 HeritageItem 청킹 → 임베딩 → 적재."""
    text = item.description or ""
    if not text.strip():
        upsert_metadata(db, item.id, EmbeddingStatus.FAILED, "description 없음")
        db.commit()
        return

    try:
        chunks = chunk_text(text)

        # 기존 vector_documents 삭제 (재처리 시 중복 방지)
        db.query(VectorDocument).filter_by(heritage_item_id=item.id).delete()

        for idx, chunk in enumerate(chunks):
            embedding = get_embedding(client, chunk)
            db.add(VectorDocument(
                heritage_item_id=item.id,
                chunk_index=idx,
                content=chunk,
                embedding=embedding,
            ))
            time.sleep(DELAY)

        upsert_metadata(db, item.id, EmbeddingStatus.DONE)
        db.commit()

    except Exception as e:
        db.rollback()
        upsert_metadata(db, item.id, EmbeddingStatus.FAILED, str(e))
        db.commit()
        raise


def run(retry_failed: bool = False) -> None:
    client = OpenAI()
    db = SessionLocal()

    try:
        items = get_pending_items(db, retry_failed)
        total = len(items)

        if total == 0:
            print("처리할 항목 없음.")
            return

        print(f"총 {total}건 임베딩 시작 (retry_failed={retry_failed})")
        success, fail = 0, 0

        for i, item in enumerate(items, 1):
            try:
                process_item(client, db, item)
                print(f"[{i}/{total}] ✅ {item.name} ({len(chunk_text(item.description or ''))}청크)")
                success += 1
            except Exception as e:
                print(f"[{i}/{total}] ❌ {item.name}: {e}")
                fail += 1

        print(f"\n완료: 성공 {success}건 / 실패 {fail}건")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry-failed", action="store_true", help="FAILED 상태 항목 재처리")
    args = parser.parse_args()
    run(retry_failed=args.retry_failed)