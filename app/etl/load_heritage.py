from app.db.session import SessionLocal
from app.db.models import HeritageItem
from app.etl.heritage_api import fetch_all


def load():
    items = fetch_all()
    db = SessionLocal()
    try:
        new_count = 0
        skip_count = 0
        for raw in items:
            exists = db.query(HeritageItem).filter_by(external_id=raw.external_id).first()
            if exists:
                skip_count += 1
                continue
            db.add(HeritageItem(
                source=raw.source,
                external_id=raw.external_id,
                name=raw.name,
                category=raw.category,
                description=raw.description,
            ))
            new_count += 1
        db.commit()
        print(f"완료: {new_count}건 적재, {skip_count}건 스킵(중복)")
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    load()
