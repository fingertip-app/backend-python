# Agent v1 계약 (Task 1)

이 디렉터리의 JSON 예제와 JSON Schema는 Python/Spring 공통 wire 계약이다. Task 1은 모델·fixture만 추가한다. 신규 endpoint, 인증 필터, catalog 조회, LangGraph 실행은 아직 구현하지 않는다. 기존 endpoint를 수정하지 않는다.

## 예정된 경로

- Python `POST /api/v1/ai/agent/recommendations`: 기존 `X-Internal-Api-Key` 인증.
- Spring `POST /v1/ai/agent/recommendations`: 인증된 사용자만 허용하고 기존 `ApiResponse` 안에 응답을 넣는다.
- Spring `POST /internal/ai/experiences/search`: `catalog-search.json`의 `{queryTerms, constraints, limit}` body, `X-AI-Service-Key` 인증.
- Spring `GET /internal/ai/experiences/{id}`: `detail-query.json`에 regionCode/maxPriceKrw/headCount query 예제. 같은 고정 조건을 재검증한다.
- catalog 응답은 `ApiResponse`의 data 배열 또는 객체. 정상 envelope는 `{success:true,message:"Success",data:...}`이고 errorCode는 null일 때 기존 방식대로 생략한다.

## 검증 규칙

모든 신규 JSON 객체는 unknown field를 거부한다. 기존 global mapper나 기존 DTO는 변경하지 않는다. query는 trim 후 1–500자, locale은 `ko`만 허용한다. constraints 생략 시 headCount=1, regionCode/maxPriceKrw=null이다. 명시 null constraints/locale/headCount/limit는 거부한다. culture 검색은 인원 조건을 사용하지 않는다.

지역은 SEOUL/GYEONGGI/INCHEON/BUSAN/JEJU. headCount는 정수 1–20, limit는 정수 1–10(생략 시5), ID는 양의 정수다. 문자열 정수나 소수 정수의 자동 변환을 허용하지 않는다. 문자열 금액은 부호·지수 없이 일반 십진 표기만 허용하고 소수점 두 자리 뒤의0은 추가 정밀도로 세지 않는다. 지수 표기는 JSON 숫자일 때만 허용한다. 금액은 JSON 숫자 또는 문자열을 입력받되 0 이상·소수점 유효 자리 2자리 이내의 Decimal/BigDecimal로 저장하고 문자열로 직렬화한다. 1인당 KRW이며 float로 재변환하지 않는다.

queryTerms는 1–5개, trim 후 각각1–50자. 빈 값은 전체 목록 검색으로 처리하지 않는다. catalog descriptionExcerpt 및 culture contentExcerpt는 최대1200자, culture 검색 결과는 최대5개다. catalog maxParticipants는 프로그램 정원이며 일정별 잔여 좌석 수가 아니다.

status는 completed/no_match/clarification_required/degraded. recommendation ID 목록은 중복 없이 recommendation entry와 순서까지 일치한다. no_match 및 clarification_required는 추천 ID를 가질 수 없다. unsupportedConstraints가 있으면 clarification_required여야 한다. degraded는 기술 실패가 완전 성공으로 취급되지 않도록 구별한 상태이며 API 오류 400/401/403/502/503/504는 별도로 평가기에 기록한다.

구조화 조건과 자연어 조건 충돌은 clarification_required로 종료한다 (`clarification.json`). Task 1은 그 출력과 seed 기대값을 고정하며 자연어 조건 추출·충돌 탐지 런타임은 후속 Task다. 총액/1인당 예산, 지역의 모호함도 확인 질문 대상이다. 날짜/주말/시간대/휠체어 접근/언어 지원은 미지원 조건으로 반환하고 충족했다고 안내하지 않는다. 부모님 동반은 가족 관심이며 고령자 적합성 검증을 뜻하지 않는다.

모델 draft는 experienceId/reason/evidenceKeys와 cultureClaims(text/documentIds) 단위다. 문화 claim은 document ID를 필수 참조한다. 자유 숫자·가격·주소의 사실 여부를 이 schema만으로 검증했다고 주장하지 않는다. 서버의 catalog 근거 검증 및 표시 조립, 오프라인 judge/human 사실성 평가는 후속 Task다.

## 예제와 한계

`invalid-examples.json`은 두 언어의 동일 경계/unknown/null/coercion 실패 사례다. Python은 `tests/agent/test_contracts.py`, Spring은 `AgentContractTest`가 동일 예제로 JSON 왕복을 검증한다. Spring test resources에는 예제의 동일 복사본이 들어간다. JSON Schema의 validation/serialization 모드도 저장해 숫자 입력과 문자열 출력의 차이를 명시한다.

이 예제의 101–112 ID는 fixture 전용이며 실제 서비스 ID가 아니다. 평가 seed와 합성 문화 자료의 상세 provenance/분할/해시 규칙은 `evaluation/seeds/v1/README.md`(Python 저장소)에 기록한다. 이 단계의 테스트 통과는 계약과 seed 무결성만 입증하며 검색·모델·AI 품질 측정 결과가 아니다.

Python의 `parse_contract_json(raw_body)`는 숫자 토큰을 Decimal로 읽는다. 모든 신규 strict model의 `model_validate_json` 및 dataset/corpus loader도 이를 사용한다. 향후 FastAPI Agent route는 request.body() 원문을 이 진입점으로 읽어야 한다. 기본 JSON parser가 float로 바꾼 뒤 모델만 검증하면 원래 금액/초과 정밀도를 복구할 수 없다. `decimal-wire-examples.json`은 큰 금액·원문 숫자 정밀도·지수/문자열 표기 경계를 두 언어에서 고정한다.
