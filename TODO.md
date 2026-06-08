# FastAPI AI Server TODO - 2026-06-28 MVP

## 책임 범위

`backend_python/`은 Spring Boot가 내부 호출하는 AI 전용 서버입니다. 인증, 예약, 결제, 알림 API는 Spring의 책임이며 FastAPI에서 새로 구현하지 않습니다.

## MVP 완료 기준

- 무형유산 데이터가 정제되어 pgvector에 저장되고, 질문별 관련 문서와 출처를 검색할 수 있다.
- Spring 내부 요청에 대해 문화 해설, 출처, 매칭 키워드와 추천 카테고리를 반환한다.
- 후기 텍스트의 1차 요약과 핵심 영어 번역을 반환한다.
- 응답 지연, OpenAI 오류, 검색 결과 없음에 대한 실패 정책과 테스트가 있다.

## 일정

### 5/27 - 5/31: 서버 역할과 데이터 계약 동결

- [x] [영진] Spring-FastAPI 내부 API 계약 확정: request/response, 오류, timeout, 인증 방식
- [x] [서영] AI 소유 테이블/인덱스 확정: heritage_items, vector_documents, embedding metadata
- [x] [서영] 공공데이터 원천과 MVP 적재 범위 확정: 국가무형유산 종목 설명과 보유자 기본 정보 우선
- [x] [공통] 기존 bookings/cardnews/experiences 외부 API 스캐폴드와 서비스 도메인 모델 제거
- [x] [영진] AI 실패 정책과 fallback 구현 완료
  - [x] OpenAI 호출 실패 시 정의된 fallback 응답 반환
  - [x] timeout/error mapping 기준 정리
  - [x] Spring 연동 시 사용할 실패 응답 형태 고정

완료 기준: Spring이 사용할 AI API 예제와 데이터 적재 대상 문서가 승인된다.

### 6/1 - 6/7: ETL과 벡터 검색 기반

- [x] [서영] pgvector 마이그레이션과 검색 인덱스 적용
  - [x] `heritage_items`, `vector_documents` 테이블 생성/검증
  - [x] embedding 컬럼 차원과 ivfflat/hnsw 인덱스 방식 확정
  - [x] 로컬/배포 DB 재실행 가능한 migration 흐름 확인git status
- [x] [서영] 공공데이터 수집/정제/중복 제거 ETL 구현
  - [x] 국가무형유산 종목 설명 데이터 수집
  - [ ] 보유자/전승자 기본 정보 수집
  - [x] 동일 종목/동일 문서 중복 제거 기준 적용
  - [x] [결정필요] MVP 적재 범위가 부족하면 수작업 데모 데이터 보강 여부 결정(구술 자서전 34건 추가)
- [ ] [서영] 임베딩 생성 배치와 재실행 가능한 적재 흐름 구현
  - [x] 문서 chunking 기준 정의
  - [ ] embedding metadata에 source/title/category 저장
  - [x] 실패한 문서만 재처리할 수 있는 batch 옵션 추가
- [ ] [영진] 설정/로그/내부 인증/health check 정리
  - [ ] OpenAI, DB, Spring internal auth 환경변수 검증
  - [ ] `/health`에서 DB 연결과 AI 설정 상태 분리 표시
  - [ ] 모델 호출 request id/logging 정리
- [ ] [공통] ETL 및 검색 smoke test 작성
  - [ ] 대표 키워드로 top-k 검색 결과 확인
  - [ ] 검색 결과 없음 케이스 확인
  - [ ] CI 또는 로컬 smoke command 문서화

완료 기준: 대표 데이터셋이 적재되고 질문에 대해 상위 문화 문서를 검색할 수 있다.

### 6/8 - 6/14: RAG 해설과 관련 체험 반환

- [ ] [영진] 질문 임베딩 -> pgvector top-k 검색 -> GPT 문화 해설 흐름 구현
  - [ ] 검색 context 조립 방식 구현
  - [ ] 출처 기반 답변 prompt 작성
  - [ ] 모델 응답 schema validation 적용
- [ ] [영진] 출처 정보가 포함된 `/api/v1/ai/explain` 실제 응답 구현
  - [ ] explanation, sources, matched_keywords, recommended_categories 반환
  - [ ] 검색 결과 없음 시 fallback 응답 반환
  - [ ] Spring client와 timeout 기준 재확인
- [ ] [서영] 체험 연결용 유사도 검색 데이터/쿼리 구현
  - [ ] 문화유산 category와 체험 category 매핑 초안 작성
  - [ ] 추천 카테고리 후보와 매칭 키워드 산출 기준 정리
  - [ ] [결정필요] Spring `Experience.category` 추가 여부에 맞춰 반환 필드 조정
- [ ] [영진] Spring 내부 호출 연동을 지원하고 mock 응답을 제거
  - [ ] 기존 mock response 제거
  - [ ] 실제 DB/vector 검색 기반 응답으로 교체
  - [ ] Spring 통합 테스트용 fixture 제공
- [ ] [공통] 출처 없음, 모델 실패, timeout 테스트 추가
  - [ ] OpenAI failure
  - [ ] vector search empty result
  - [ ] Spring timeout/fallback

완료 기준: Spring 경유 질문에서 실제 해설, 출처, 매칭 키워드와 추천 카테고리가 반환된다.

### 6/15 - 6/21: 후기 요약과 번역 최소 기능

- [ ] [서영] 후기 요약/감성 키워드 결과 스키마와 품질 샘플 마련
  - [ ] 리뷰 원문 샘플 수집
  - [ ] summary, sentiment_keywords, highlights 응답 구조 정의
  - [ ] 부정/중립/긍정 샘플별 기대 결과 작성
- [ ] [영진] 후기 요약 내부 API 구현
  - [ ] Spring에서 전달한 review batch 요약
  - [ ] 빈 리뷰/짧은 리뷰 fallback 처리
  - [ ] 요약 결과 schema validation 적용
- [ ] [영진] 핵심 AI 해설 영어 번역 API 또는 locale 응답 구현
  - [ ] [결정필요] 별도 번역 API와 `/explain?locale=en` 중 구현 방식 확정
  - [ ] 영어 번역 결과와 원문 출처 연결 유지
  - [ ] 번역 실패 시 한국어 원문 fallback
- [ ] [공통] 개인정보성 입력 필터와 모델 호출 실패 처리 점검
  - [ ] 전화번호/이메일 등 개인정보성 입력 처리 기준 정리
  - [ ] 모델 실패 시 Spring 저장 정책 확인
  - [ ] 후기 요약/번역 통합 테스트 작성

완료 기준: 후기 샘플 요약과 영어 해설 결과가 Spring을 통해 조회된다.

### 6/22 - 6/28: 성능 점검과 시연 데이터 고정

- [ ] [서영] 데모용 데이터 적재본, 재적재 절차, 검색 결과 품질 점검
  - [ ] 시연 질문별 기대 검색 결과 고정
  - [ ] 재적재 command와 소요 시간 기록
  - [ ] 출처 누락/부정확 응답 샘플 수정
- [ ] [영진] 응답 시간/timeout/fallback 정책과 운영 로그 점검
  - [ ] explain/review/translate API 응답 시간 측정
  - [ ] timeout, retry, fallback 로그 확인
  - [ ] Spring 장애 대응 문서와 맞춰 최종 점검
- [ ] [공통] 카드뉴스 -> 해설 -> 추천 체험 통합 시나리오 검증
  - [ ] 카드뉴스 id 기반 질문 흐름 확인
  - [ ] 해설 하단 추천 카테고리/체험 연결 확인
  - [ ] 실제 기기 또는 프론트 앱에서 E2E 확인
- [ ] [공통] 시연 중 외부 모델 장애에 대비한 고정 데모 fallback 준비
  - [ ] 대표 질문 fallback 응답 고정
  - [ ] 외부 모델 차단 상태에서 시연 경로 검증
  - [ ] 시연 직전 데이터/환경변수 freeze

완료 기준: 대표 질문 시나리오가 안정적으로 응답하고 6/28 시연 데이터가 고정된다.

## 마감 이후 항목

- 개인화 추천과 협업 필터링
- 자동 카드뉴스 생성 파이프라인
- 일·중 문화 맥락 번역 고도화 및 대규모 벡터 검색 튜닝
