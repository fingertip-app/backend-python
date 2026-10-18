# 로컬 Docker DB 연결

2026-10-18 확인. 기존 Spring Compose의 PostgreSQL과 Redis를 사용한다.

```bash
cd ../backend
docker compose up -d postgres redis
cd ../backend_python
export DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5433/janginharou'
export REDIS_URL='redis://127.0.0.1:6379/0'
.venv/bin/uvicorn app.main:app --reload
```

환경변수는 해당 터미널에서 `.env`보다 우선한다. 기존 `.env`의 원격 DB 주소와 키를 수정할 필요가 없다. 위 계정 정보는 저장소 Compose에 정의된 로컬 개발용이다.

Python SQLAlchemy에서 `SELECT 1` 성공. PostgreSQL pgvector 확장 설치 확인. Docker 데이터 볼륨 삭제 없음.

최초 확인 시 장인·체험·문화유산은 각각 0건이었다. 이후 `scripts.prepare_local_ai_db`로 누락 AI 테이블과 검색 인덱스를 준비했다. Alembic 이력은 변경하지 않았다.

```bash
DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5433/janginharou' \
  .venv/bin/python -m scripts.prepare_local_ai_db
DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5433/janginharou' \
  .venv/bin/python -m scripts.pottery_local_smoke --offline
```

오프라인 검증은 `[테스트]` 가상 장인 1명과 체험·문화 항목·청크 각각 2건을 로컬에 남긴다. 예약 일정은 만들지 않는다. 합성 단위 벡터로 검색 경로만 검증하므로 실제 의미 검색 품질을 증명하지 않는다. 이 로컬 DB는 데모·검증용이며 실제 사용자에게 노출하지 않는다.

최초 실제 모델 호출은 `AuthenticationError`로 실패했으나, 사용자 키 갱신 후 `--offline` 없이 재실행해 성공했다. 합성 벡터를 실제 임베딩으로 갱신했고 청자 우선 검색·LLM 답변·출처 2건 반환을 확인했다. 합성 콘텐츠에 대한 연결 점검이며 실서비스 추천 품질 평가는 별도다. 키는 채팅이나 저장소에 기록하지 않는다.

이미 `heritage_items`가 있으므로 검토 없이 `alembic upgrade head`를 실행하면 기준 마이그레이션의 테이블 생성과 충돌할 수 있다. 로컬 보완 도구는 배포용 마이그레이션을 대체하지 않는다. 기존 테이블을 삭제하거나 무조건 이력을 stamp하지 않는다.
