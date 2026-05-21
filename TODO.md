# Backend TODO

## 공통

- [ ] [공통] API 명세 확정: 인증, 장인, 체험, 예약, 결제, 후기, 카드뉴스, AI 검색 응답 포맷
- [ ] [공통] ERD 확정: users, artisans, heritage_items, experiences, bookings, payments, reviews, card_news, vector_documents
- [ ] [공통] `.env` 값 정리: DB, Redis, OpenAI, Toss, Kakao, AWS, JWT
- [ ] [공통] GitHub Actions CI 구성: lint, test, migration check

## 영진

- [ ] [영진] 전체 백엔드 아키텍처 리뷰 및 API/앱 통합 기준 정리
- [ ] [영진] 문화재청/국가유산포털/문화 빅데이터/Tour API 수집 어댑터 설계
- [ ] [영진] RAG 검색 흐름 구현: 질문 임베딩 -> pgvector 검색 -> GPT 해설 생성
- [ ] [영진] 한물결 카드뉴스 AI 생성 파이프라인 설계
- [ ] [영진] 앱-백엔드 통합 테스트 케이스 리뷰

## 서영

- [ ] [서영] PostgreSQL + pgvector 스키마 작성
- [ ] [서영] Alembic 초기 마이그레이션 작성
- [ ] [서영] 공공데이터 ETL 정제 스크립트 구현
- [ ] [서영] heritage/vector document 임베딩 생성 배치 구현
- [ ] [서영] 후기 감성 분석/키워드 요약 데이터 모델 구현
- [ ] [서영] 벡터 검색 인덱스 성능 튜닝

## 지현

- [ ] [지현] FastAPI 라우터 구현: auth, artisans, experiences, bookings, reviews, admin
- [ ] [지현] 장인 인증 신청/승인 플로우 구현
- [ ] [지현] 예약 요청/승인/거절/확정 상태머신 구현
- [ ] [지현] Toss Payments 결제 요청 및 webhook 검증 구현
- [ ] [지현] Celery 작업 구성: 임베딩, 번역, 알림, 후기 요약
- [ ] [지현] AWS EC2/RDS/Redis 배포 문서 및 환경 구성

## MVP API Acceptance

- [ ] 사용자는 추천 체험 목록을 조회할 수 있다
- [ ] 사용자는 자연어 질문으로 문화 해설과 관련 체험을 받을 수 있다
- [ ] 사용자는 체험 상세에서 날짜/인원을 선택해 예약 요청을 만들 수 있다
- [ ] 장인은 예약 요청을 승인/거절할 수 있다
- [ ] 관리자는 장인 인증 신청과 카드뉴스를 관리할 수 있다
