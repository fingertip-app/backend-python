# 장인과 하루 LangGraph 에이전트·반복 평가 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 이 문서는 구현 계획이며, 실행·커밋·배포 또는 병렬 에이전트 작업을 시작하지 않는다.

**Goal:** 기존 RAG를 비교 기준으로 보존하면서, 도구를 선택·호출·재검증하는 체험 추천 에이전트와 재현 가능한 반복 평가를 추가한다.

**Architecture:** FastAPI는 LangGraph 실행과 문화 자료 검색을 담당한다. 체험의 가격·활성 상태·정원·주소·태그는 Spring의 새 내부 조회 API에서 가져온다. 최종 추천은 서버가 확인한 ID와 사실 필드로 조립하며, 기존 API는 유지한다.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, pgvector, OpenAI, LangGraph StateGraph, langchain-openai; 기존 Java/Spring Boot/JPA; pytest, 기존 Spring 테스트 도구.

## Global Constraints

- 범위는 `fingertip-app/backend-python`과 `fingertip-app/backend`이다. bplus는 제외한다.
- 조사 기준: Python `develop` = `cf9cd219b8baabcbc8079dbe6c30cdc04e5e126e`; Spring `develop` = `58b712a69277c2c0e3887f51bc20c861a6706f01`.
- 구현 시작 시 두 SHA와 로컬 변경을 다시 기록한다. 기준이 바뀌면 아래 파일·계약을 재대조한다.
- 새 브랜치 이름에는 `codex/`를 붙이지 않는다. 후보: `feat/langgraph-agent-evaluation`.
- 기존 `/api/v1/ai/explain`, `/api/v1/ai/recommendations`, Spring `/v1/ai/recommendations`의 요청·응답 계약을 유지한다.
- 첫 버전은 단일 에이전트, 요청 단위 상태, 한국어 응답, 읽기 전용 도구 3개로 구현한다.
- 예약 실행·결제·일정별 잔여 좌석 조회는 범위 밖이다. `maxParticipants`는 프로그램 정원이고 예약 가능한 좌석 수가 아니다.
- 멀티턴 영구 저장·SSE·멀티에이전트·클라우드 평가 업로드는 후속 범위다. 첫 버전에서 작동한다고 주장하지 않는다.
- 모델은 `AGENT_MODEL`로 기존 `OPENAI_GENERATION_MODEL`과 같은 값부터 시작한다. 도구 호출·구조화 출력 지원 여부를 첫 실험에서 확인한다.
- 도구 호출은 순차 실행한다. SQLAlchemy Session을 LangGraph State 또는 병렬 노드에 넣지 않는다.
- 재검색/답변 수정은 합산 최대 2회, 도구 호출 최대 6회, 모델 호출 최대 6회, 그래프 recursion_limit 32, 전체 실행 목표 상한 45초다. 한도를 넘으면 종료한다.
- 공급자 자동 재시도는 0으로 시작해 호출 횟수·시간을 정확히 측정한다. 네트워크 호출별 timeout은 남은 요청 예산과 설정값 중 작은 값이다. 개별 제한의 누적으로 전체 예산을 넘기지 않는다.
- 가격은 KRW 1인당 금액으로 취급한다. Spring BigDecimal과 Python Decimal/문자열로 전송하고 float 변환을 피한다.
- Python 서비스 도메인 테이블의 쓰기·새 마이그레이션은 추가하지 않는다.
- 기존 개인정보 마스킹을 도구 인자·모델 입력·평가 출력에 적용한다. API 키·원문 사용자 대화는 실행 추적에 기록하지 않는다.
- 이번 계획 작성에서는 애플리케이션 코드, 원격 저장소, 환경설정을 수정하지 않았다.

## 1. 확인된 현재 구조와 설계 선택

| 기존 파일 | 확인된 동작 | 계획에 미치는 영향 |
|---|---|---|
| Python `app/services/ai/rag.py:69` | 질문 마스킹 → 임베딩 → `_search` → 자료 기반 생성, 빈 결과·언어 fallback·응답 스키마 검증 | 문화 검색 단계만 공개 메서드로 분리하여 재사용 |
| Python `app/services/ai/rag.py:167` | 벡터 후보 → 청크 제한 → lexical/IDF 순위 → 컨텍스트 제한 | 검색 알고리즘은 변경하지 않고 비교 실험에서 고정 |
| Python `app/services/ai/experience_rag.py:107` | 활성 여부·벡터 거리만 필터링하고 top-k 반환 | 에이전트의 하드 조건 검증에는 그대로 사용하지 않음. 기존 추천 비교군으로 보존 |
| Python `app/api/v1/routers/ai.py:140` | headCount·timePreference·conversationHistory를 받지만 추천에는 freeText/interests/region으로 만든 문자열만 전달 | 신규 요청에서 조건을 구조화하고 각 지원 여부를 명시 |
| Python `scripts/rag_api_smoke_test.py:22` | 6개 질문의 sources/matchingKeywords 기대값 판정 | 문화 평가 데이터셋의 최초 회귀 사례로 활용 |
| Spring `domain/ai/service/RecommendationService.java` | FastAPI의 ID를 재조회하여 이미지 등 응답 조립. 외부 호출을 readOnly transaction 안에서 실행 | 신규 서비스는 네트워크 대기 구간과 DB 읽기 트랜잭션을 분리 |
| Spring `domain/experience/entity/Experience.java` | price=BigDecimal, maxParticipants, locationAddress, tags, isActive | Spring 내부 조회 DTO를 사실의 기준으로 사용 |
| Python `app/db/models.py:68` | Experience.price=Integer, 좌표=String. Spring과 완전히 같은 모델이 아님 | 새 에이전트에 이 ORM을 확장하지 않음 |
| Spring `global/config/FastApiProperties.java` | 기본 readTimeoutMs=15000 | 기존 설정을 전체 상향하지 않고 agent 전용 timeout/client 추가 |

비교한 접근:

1. **별도 단일 에이전트 + Spring 조회 도구 — 추천.** 기존 비교군을 보존하고 실패·재시도·데이터 경계를 설명하기 좋다. 두 저장소의 작은 계약 추가가 필요하다.
2. 기존 RAG를 고정 노드 순서로 감싸기. 변경량은 적지만 동적 도구 선택 경험을 충분히 보여주기 어렵다.
3. 여러 전문 에이전트로 분리하기. 현재 문제에는 호출량·상태 관리가 늘어난다. 단일 에이전트의 품질을 먼저 확인한다.

## 2. 신규 API와 데이터 계약

### 요청/응답

- Python 내부 API: `POST /api/v1/ai/agent/recommendations` — 기존 `X-Internal-Api-Key` 인증 재사용.
- Spring 외부 API: `POST /v1/ai/agent/recommendations` — 초기에는 인증된 사용자만 허용. 기존 추천 API의 공개 여부를 복사하지 않는다.
- Spring 도구 API: `POST /internal/ai/experiences/search`, `GET /internal/ai/experiences/{id}`.
- 내부 도구 API는 agent 전용 서비스 키 `X-AI-Service-Key`로 보호한다. JWT 없이 내부 인증 필터가 이 정확한 경로에만 인증 객체를 설정한다. 기존 JWT 인증과 다른 경로의 권한은 유지한다.
- FastAPI가 Spring의 외부 AI API를 재호출하지 않는다. 내부 catalog API는 Experience 조회 서비스에만 연결해 호출 순환을 막는다.

신규 요청 예시:

```json
{
  "query": "서울에서 부모님과 한지 체험을 하고 싶어요. 1인당 5만원 이하로요",
  "locale": "ko",
  "constraints": {"regionCode": "SEOUL", "maxPriceKrw": "50000", "headCount": 3}
}
```

- query: 1~500자; locale: v1은 ko만; headCount: 1~20; maxPriceKrw: 0 이상, 소수 2자리 이내 Decimal.
- 구조화 필드와 자연어 조건이 충돌하면 `clarification_required`로 종료한다. 명시 조건을 LLM이 넓히거나 삭제할 수 없다.
- 구조화 조건이 없으면 별도 모델 호출에서 typed intent를 추출한다. 모호한 예산 단위(총액/1인당)와 지역은 확인 질문으로 종료한다.
- v1 지역 코드: SEOUL/GYEONGGI/INCHEON/BUSAN/JEJU. 주소의 시·도 접두어와 매핑한다. 미지원 지역은 확인 질문, 주소가 없는 항목은 지역 제한 요청에서 제외한다.
- 날짜·주말·시간대·휠체어 접근·언어 지원 등 v1 미지원 조건은 `unsupportedConstraints`에 반환하고 확인 질문으로 종료한다. 충족했다고 안내하지 않는다.
- ‘부모님과’는 가족 관심 맥락으로 사용하며 고령자 적합성이 검증됐다는 사실로 변환하지 않는다.

Python 응답 계약:

```json
{
  "status": "completed",
  "answer": "조건에 맞는 한지 체험을 확인했습니다.",
  "recommendedExperienceIds": [101],
  "recommendations": [{"experienceId": 101, "reason": "한지 만들기 체험", "evidenceKeys": ["experience:101:title"]}],
  "sources": [],
  "appliedConstraints": {"regionCode": "SEOUL", "maxPriceKrw": "50000", "headCount": 3},
  "unsupportedConstraints": [],
  "limitations": ["일정별 잔여 좌석은 확인하지 않았습니다."],
  "requestId": "agent-demo-001"
}
```

- status는 `completed | no_match | clarification_required | degraded`.
- 기술 실패·예산 초과가 빈 추천 정상 성공으로 바뀌지 않는다. API 오류는 400/401/403/502/503/504로 분리하고 평가기에 그대로 기록한다.
- 모델의 draft에는 숫자·ID·가격·주소를 임의 자유 서술하지 않고 `experienceId`, `reason`, `evidenceKeys`, 문화 답변/claim 단위를 구조화하여 받는다.
- 가격·지역·정원 표시는 검증한 catalog DTO에서 서버가 렌더링한다. culture claim은 retrieved document ID를 필수로 참조한다. 구조 검증과 별도로 사실성 평가는 오프라인 judge/human으로 수행한다.
- Spring 외부 응답은 기존 `ApiResponse` envelope 안에 신규 Agent 응답 DTO를 넣고 최종 조회한 제목·가격·이미지를 조립한다.

### 도구 계약

| 도구 | 입력 | 출력 | 검증 |
|---|---|---|---|
| search_culture_documents | query 1~500자 | 최대 5개 문서: documentId/heritageId/title/source/category/contentExcerpt | 기존 검색 결과를 직렬화. excerpt 문서당 1200자 |
| search_experiences | queryTerms 1~5개(각 1~50자), limit 1~10 | catalog items: id/title/descriptionExcerpt/tags/priceKrw/maxParticipants/regionCode/isActive | 지역·가격·인원은 State의 고정 조건을 서버가 주입. 모델 인자로 받지 않음 |
| get_experience_details | experienceId | 동일 DTO와 상세 설명 | active 여부와 고정 조건을 다시 검증. 비활성/없는 ID는 not_found |

Spring search는 active + 가격 + 인원 + 지역 필터를 **limit보다 먼저** 적용한다. 검색어 중 하나 이상이 title/description/tags에 일치하는 항목을 찾고 태그/제목 일치 점수 후 id로 안정 정렬한다. 빈 검색어는 전체 목록 조회로 처리하지 않는다. 검색어 `%`, `_`는 LIKE literal escape한다. v1 추천 검색은 lexical catalog 검색이라는 점을 평가 보고서에 명시한다.

## 3. 파일 변경 지도

Python 새 파일:

- `app/schemas/agent.py`: 요청·응답·Constraints·CatalogExperience·RetrievedDocument·AgentDraft·Intent 모델.
- `app/services/ai/agent/state.py`: 그래프 State와 실행 카운터.
- `app/services/ai/agent/model.py`: ChatOpenAI tool binding, intent 추출, draft 구조화, 토큰/latency 기록.
- `app/services/ai/agent/catalog.py`: 고정 Spring URL의 내부 API client. Runtime 설정으로만 URL 결정.
- `app/services/ai/agent/tools.py`: 세 도구의 registry/인자 검증/고정 조건 주입.
- `app/services/ai/agent/graph.py`: StateGraph 노드·분기·종료 경로.
- `app/services/ai/agent/validation.py`: 근거 ID/추천 조건 검사와 서버 응답 조립.
- `app/services/ai/agent/service.py`: 요청별 그래프 구성·invoke·timeout·결과 변환.
- `app/prompts/agent_recommendation.md`: 도구 선택·검색 실패·근거 사용 정책.
- `app/api/v1/routers/agent.py`: 내부 인증, Depends와 얇은 route.
- `evaluation/{dataset.py,targets.py,evaluators.py,runner.py,report.py}`: 평가 전용 패키지.
- `evaluation/datasets/{culture_v1.jsonl,recommendation_v1.jsonl,catalog_v1.json,human_labels_v1.jsonl}`: 고정 질의와 합성 체험 fixture, 사람이 매긴 정답.
- `scripts/evaluate_agent.py`: 평가 CLI.
- `tests/agent/{test_contracts.py,test_tools.py,test_graph.py,test_validation.py,test_api.py}`; `tests/evaluation/{test_runner.py,test_evaluators.py}`.

Python 수정 파일:

- `app/services/ai/rag.py`: 공개 `retrieve_documents(db, query, limit=5)` 추가. 기존 `_embed/_search` 재사용, explain 출력 유지.
- `app/api/v1/router.py`: agent router 등록.
- `app/core/config.py`, `.env.example`: enable/model/limit/timeout/catalog 설정 추가.
- `pyproject.toml`, `uv.lock`: langgraph, langchain-openai, httpx를 runtime 의존성에 추가. 호환 버전은 Python 3.11 환경에서 resolve 후 lock으로 고정; unrelated upgrade는 배제.
- `.gitignore`: `evaluation/results/` 제외. README와 신규 `docs/agent-api-contract.md`, `docs/agent-evaluation.md`에 실행법 기록.

Spring 경로는 `src/main/java/com/janginharou/` 기준:

- 신규 `domain/ai/controller/AgentRecommendationController.java`, `domain/ai/service/AgentRecommendationService.java`, `domain/ai/dto/{AgentRecommendationRequest,AgentRecommendationResponse}.java`.
- 신규 `domain/ai/controller/InternalAiCatalogController.java`, `domain/ai/service/InternalAiCatalogService.java`, `domain/ai/dto/{CatalogSearchRequest,CatalogExperienceResponse}.java`.
- 신규 `global/client/AgentFastApiClient.java`, `global/config/AgentAiProperties.java`, `global/security/AiServiceKeyAuthenticationFilter.java`.
- 수정 `domain/experience/repository/ExperienceRepository.java`: catalog 검색용 bounded query/custom repository 추가.
- 수정 `global/config/SecurityConfig.java`, `src/main/resources/application.yml`: 정확한 내부 경로 인증·agent client 설정.
- 대응 테스트는 `src/test/java/com/janginharou/domain/ai/`와 `global/client/`, `global/security/`에 추가.

## Task 1: 계약·기준 응답·평가 데이터 고정

**Deliverable:** 두 저장소가 같은 agent JSON을 해석하고 기존 비교군과 실험 데이터를 식별할 수 있다.

- [ ] 신규 Pydantic/Java DTO 작성 전 요청 범위·enum·Decimal·충돌 조건 실패 테스트 작성.
- [ ] 기존 6개 smoke 질의를 culture dataset에 가져오고 총 20개로 확장한다: 정확명/자연어 표현/모호 질문/무관 질문 각각 5개.
- [ ] 추천 dataset 20개 작성: 정상/가격 경계/지역·인원 경계/무결과·비활성·모호 조건 각각 5개. 각 사례에 supported mode와 allowedIds, forbiddenIds, expectedStatus 기록.
- [ ] 합성 catalog 12개 구성: 지역 3종, 가격 경계값 50000/50000.01/49999.99, 정원 2/3/4, active/inactive, 빈 주소를 포함한다. ID는 fixture 전용 101~112.
- [ ] 문화 expected source는 고정된 실제 heritage snapshot의 ID를 사용한다. 사람이 모든 질의의 정답 문서를 확인하고 snapshot_hash에 기록한다.
- [ ] dataset에 dev/test 각 10개를 명시한다. 동일 질문의 표현 변형은 같은 split에 배정한다.
- [ ] 기존 endpoint의 대표 응답 JSON과 오류를 보존 테스트로 고정한다.

계약 테스트 예시(신규 모델 위치 확정):

```python
from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.schemas.agent import AgentConstraints

def test_price_preserves_decimal_boundary():
    value = AgentConstraints(maxPriceKrw="50000.01", headCount=3)
    assert value.maxPriceKrw == Decimal("50000.01")

def test_head_count_rejects_zero():
    with pytest.raises(ValidationError):
        AgentConstraints(headCount=0)
```

**Validation:** `uv run pytest tests/agent/test_contracts.py -q`; Spring 신규 DTO validation tests. 완료 기준은 두 언어의 JSON 직렬화와 경계값 테스트 통과다.

## Task 2: Spring 읽기 전용 catalog API

**Consumes:** Task 1의 Constraints/Catalog DTO. **Produces:** 두 내부 API와 fixture 호환 응답.

- [ ] service key 미설정 503·누락 401·불일치 403·정상 성공, 다른 경로의 권한에 영향이 없는지 먼저 테스트한다.
- [ ] `InternalAiCatalogService.search(request)`와 `getDetail(id, constraints)`를 구현한다. DB 트랜잭션은 각 호출의 짧은 readOnly 구간으로 제한한다.
- [ ] 필터를 limit 전에 적용한다. 상위 조건 불일치 항목이 다수 있어도 조건에 맞는 항목을 찾는 테스트를 작성한다.
- [ ] BigDecimal 비교, active=false, null address, 정원 부족, 여러 태그에 의한 중복, LIKE wildcard를 검증한다.
- [ ] 제목/태그 일치 점수 → ID 순서, 최대 10개, null 허용 필드를 고정한다.
- [ ] 내부 인증 필터를 지정 경로에만 적용한다. catalog 서비스가 AI 서비스를 호출하지 않는지 검증한다.
- [ ] DB 조회 timeout 2초와 connection acquisition timeout을 실험 환경에 적용한다. 각 조회를 끝내고 응답 DTO로 변환한 뒤 연결을 반환한다.

**Validation:** `./gradlew test --tests '*InternalAiCatalog*' --tests '*AiServiceKey*'`. 이 작업에서는 일정별 예약 가능 여부를 판단하지 않는다.

## Task 3: Python 검색·catalog를 세 도구로 제공

**Interfaces:** `CultureRagService.retrieve_documents(db: Session, query: str, limit: int = 5) -> list[RetrievedDocument]`; `CatalogClient.search(query_terms: list[str], constraints: AgentConstraints, limit: int = 5) -> list[CatalogExperience]`; `CatalogClient.get_detail(id: int, constraints: AgentConstraints) -> CatalogExperience | None`.

- [ ] 공개 retrieve 메서드가 같은 limit의 기존 검색과 동일한 순서·출처를 반환하는 회귀 테스트를 먼저 작성한다.
- [ ] `_embed/_search` 알고리즘을 유지하고 마스킹한 query를 serialized document로 변환하는 wrapper를 추가한다. 기존 explain 생성 경로는 그대로 둔다.
- [ ] catalog client에 고정 base URL, 인증, timeout, 응답 스키마 검증을 적용한다. httpx를 runtime 의존성으로 이동한다.
- [ ] 세 tool definition과 Pydantic 인자 schema를 정의한다. 지역·예산·인원은 도구 인자에서 제외하고 request State에서 주입한다.
- [ ] 허용되지 않은 도구, 음수 ID, 빈 검색어, 잘못된 JSON, catalog timeout·401/403·5xx를 구분한다.
- [ ] runtime context로 db factory와 client를 주입한다. State에는 직렬화 가능한 DTO와 messages만 저장한다.
- [ ] 문화 검색 도구는 호출마다 DB 세션을 열고 자료를 DTO로 만든 뒤 닫는다. 모델 응답을 기다리는 동안 DB 연결을 보유하지 않는다.

**Validation:** `uv run pytest tests/agent/test_tools.py tests/test_rag.py -q`. mock의 오류 전파 검사와 로컬 catalog 계약 검사를 구분한다.

## Task 4: LangGraph 동적 실행과 최종 검증

**Interfaces:** `AgentService.run(request: AgentRequest, request_id: str) -> AgentResponse`; `validate_draft(draft: AgentDraft, catalog: dict[int, CatalogExperience], docs: dict[int, RetrievedDocument], constraints: AgentConstraints) -> list[str]`.

State 필드: messages, intent, immutable constraints, documents, catalog, draft, validationErrors, modelCalls, toolCalls, repairCount, deadline, traceEvents. messages는 add_messages reducer를 사용하고 tool_call_id를 대응시킨다.

```text
START -> extract_intent -> planner
planner -- tool_calls --> tools -> planner
planner -- answer_ready --> build_draft -> validate
planner -- ambiguous --> clarification -> END
validate -- valid --> assemble_response -> END
validate -- invalid AND repairCount < 2 --> planner
validate -- invalid AND repairCount >= 2 --> degraded -> END
모든 단계 -- 호출/시간 예산 초과 --> degraded / 504
```

- [ ] ScriptedModel과 fake tools로 문화 질문 → culture tool, 추천 → catalog, 검색 실패 → 검색어 변경 후 재검색을 먼저 테스트한다.
- [ ] ChatOpenAI.bind_tools를 사용하는 planner와 StateGraph를 구현한다. 모델이 필요한 도구를 선택하게 하고 모든 도구를 고정 순서로 실행하지 않는다.
- [ ] 관련 자료/체험 조회가 성공하기 전에는 answer_ready를 받아들이지 않는다. 추천 draft의 ID는 조회한 active catalog ID로 제한한다.
- [ ] 중복 ID, 미조회 ID, 예산·지역·정원 불일치, 출처 불일치를 검증한다. 최종 추천은 최대 5개다.
- [ ] reason의 evidenceKeys는 실제 필드에, culture claim의 documentId는 검색한 자료에 대응시킨다. 자유 서술의 의미적 정확성은 별도 오프라인 평가에서 측정한다.
- [ ] 검증 오류를 planner에 전달해 재검색 또는 draft 수정을 수행한다. repairCount 증가와 모든 분기의 종료 한도를 테스트한다.
- [ ] 요청마다 새 State를 생성하고 다른 요청의 catalog/messages가 혼합되지 않는지 검증한다.
- [ ] tokens, 실제 model, node 순서, tool name, elapsedMs, failureKind를 기록한다. 내부 추론문을 요청하거나 저장하지 않는다.

**Validation:** `uv run pytest tests/agent/test_graph.py tests/agent/test_validation.py -q`. mock으로 모든 분기를 확인하고 실제 품질은 Task 7에서 검증한다.

## Task 5: FastAPI와 Spring 신규 경로 연결

- [ ] `agent.py`의 route를 sync `def`로 추가하고 graph 로직을 service로 분리한다. 모델/catalog 각 호출에 남은 예산을 반영한 timeout을 적용한다.
- [ ] `AGENT_ENABLED=false`를 기본값으로 한다. disabled 503, 내부 인증, schema error, provider timeout을 HTTP 테스트한다.
- [ ] Spring에 agent 전용 client/controller/service를 추가한다. 기존 client의 자동 재시도와 15초 timeout은 재사용하지 않는다. agent read timeout은 50초, FastAPI 전체 예산은 45초 이하, connect timeout은 1초다.
- [ ] Spring AgentRecommendationService 전체에 @Transactional을 붙이지 않는다. 모델 대기가 끝난 후 독립 service의 짧은 readOnly 구간에서 최종 ID를 재조회한다.
- [ ] FastAPI 반환 후 비활성화/변경된 체험을 모든 조건으로 재검증한다. 제외 항목이 생기면 degraded와 일반 안내문으로 바꾸고 제외 ID를 언급하는 기존 answer/reason을 반환하지 않는다.
- [ ] 신규 status를 기존 fallback bool에만 대응시키지 않는다. no_match와 provider 실패를 구분한다.
- [ ] 앱 변경 없이 로컬 HTTP로 기존/신규 endpoint를 비교하는 요청 예시를 docs에 추가한다.

**Validation:** Python `tests/agent/test_api.py`; Spring `*AgentRecommendation*`, `*AgentFastApiClient*`; 로컬 인증 요청 왕복. 기존 API 계약 회귀도 확인한다.

## Task 6: 고정 데이터셋 반복 실행·규칙 평가

**Interfaces:** `EvaluationCase`는 caseId/split/task/inputs/expected/corpusHash를 가진다. `EvaluationOutput`은 status/answer/sources/recommendations/error/latencyMs/tokenUsage/trace를 가진다. `Target.run(case) -> EvaluationOutput`; `evaluate_rules(case, output) -> RuleScores`; `run_experiment(cases, targets, repetitions, seed, output_dir) -> ExperimentManifest`.

- [ ] fake target 호출 횟수가 cases×targets×repetitions인지, case별 각 반복이 별도 run인지 먼저 테스트한다.
- [ ] 실패도 포함하여 caseId/repeatIndex/variant/error/latency/tokenUsage/실제 model/commit/hash를 JSONL에 저장한다.
- [ ] culture 비교군: 기존 `/explain`과 agent culture 응답. 동일 검색 설정·snapshot·같은 문서 노출 상한을 사용한다. 기존 30 chunk와 agent 5 document 차이는 입력 조건 차이로 보고 별도 동일-context 비교도 저장한다.
- [ ] recommendation 비교군: 기존 `/recommendations`와 agent. legacy query에도 동일 조건을 자연어로 전달한다.
- [ ] 조건 필터의 효과와 에이전트 반복의 효과를 분리하려고 `single_pass_catalog`도 구현한다. 같은 catalog/hard filters/model로 한 번 검색·한 번 생성한 결과와 agent를 비교한다.
- [ ] legacy 대비 개선을 모두 LangGraph 효과로 설명하지 않는다. catalog 검색 방식과 조건 강제 차이를 보고서에 명시한다.
- [ ] source hit, expectedStatus, active, allowed/forbidden ID, Decimal 가격, 지역, 정원, schema, empty-result, latency, tokens를 코드로 판정한다.
- [ ] no_match가 정답인 case에서만 빈 결과를 성공으로 처리한다. 추천 정답이 존재하는 case의 빈 답변은 실패다.
- [ ] 기술 실패는 성공률 분모에 포함한다. judge를 실행하지 못했으면 null과 사유를 기록한다.
- [ ] 동일 질문을 다시 실행하여 실제 LLM 응답을 얻는다. 생성 응답 cache/replay는 사용하지 않는다. 고정 문서/임베딩 재사용은 양쪽에 동일 적용한다.
- [ ] seed로 case 순서를 재현하고 variant 실행 순서를 번갈아 배치한다.
- [ ] `--live` 없는 실행은 mock 검사다. live는 `--max-model-calls`, `--max-total-tokens`, output-dir가 필수이며 한도 도달 시 미실행 case를 표시하고 종료한다.
- [ ] 고정한 문화/체험 snapshot을 로컬 전용 pgvector DB와 Spring test profile에 넣는다. 일반 개발/운영 DB를 평가 과정에서 덮어쓰지 않는다. catalog fixture와 legacy Experience 테이블은 동일 ID/가격/정원/주소를 사용한다.

신규 CLI 예시(구현 완료 후 사용):

```bash
uv run python scripts/evaluate_agent.py --suite culture --split dev --variants legacy,agent --repetitions 3 --seed 42 --output-dir evaluation/results/culture-dev
uv run python scripts/evaluate_agent.py --suite recommendation --split test --variants legacy,single_pass_catalog,agent --repetitions 5 --seed 42 --live --max-model-calls 1000 --max-total-tokens 1000000 --output-dir evaluation/results/recommendation-test
```

**Validation:** `uv run pytest tests/evaluation/test_runner.py tests/evaluation/test_evaluators.py -q`. mock 집계 검사와 실제 실험 출력은 별도 디렉터리에 저장한다.

## Task 7: LLM 판정·사람 채점 대조·개선 보고

- [ ] judge 입력은 질문/검색 자료/catalog snapshot/실제 답변이다. 기대 스코어를 prompt에 넣지 않는다.
- [ ] rubric: groundedness(0/1/2), relevance(0/1/2), unsupportedClaims 목록, 근거 ID와 짧은 판정 사유. judge model과 prompt hash를 저장한다.
- [ ] 각 답변의 judge 결과를 한 번 저장한다. 판정자 변동과 agent 변동을 혼동하지 않는다. 모호한 판정은 사람이 검토하고 불일치를 남긴다.
- [ ] culture 5개·recommendation 5개에서 성공/실패가 섞이도록 고르고, 각 3repeat의 총 30출력을 사람이 같은 rubric으로 채점한다. version 이름은 가린다.
- [ ] judge/사람의 일치율·혼동 행렬·구체적인 불일치를 출력한다. judge unavailable을 groundedness=0으로 변환하지 않고 judge failed로 분리한다.
- [ ] dev split에서 실패 분류 → 한 요소 개선(tool description/검색어/재시도 조건) → 같은 dev split 재측정을 수행한다.
- [ ] test split은 개선 완료 후 사용한다. test를 보고 재조정했다면 해당 test를 최종 미사용 데이터로 부르지 않는다.
- [ ] 질문별 성공 횟수/전체 실행, run 평균, 질문별 점수 표준편차, 모든 반복이 성공한 case 비율, p50/p95 latency, 평균 tokens, 기술 실패율을 보고한다.
- [ ] 작은 실험으로 전체 사용자 품질을 보장하지 않는다. 구간 추정이 필요하면 반복 run이 아닌 case 단위 cluster bootstrap을 사용한다.
- [ ] `manifest.json`, `runs.jsonl`, `scores.jsonl`, `summary.csv`, `report.md`를 생성한다. 미측정 예시 숫자를 성과표에 넣지 않는다.

보고서 열:

```text
variant | case_count | repetitions | attempted_runs | valid_runs
rule_success_rate | all_repeats_pass_case_rate | groundedness_mean
judge_human_agreement | p50_ms | p95_ms | average_tokens | provider_failure_rate
```

## Task 8: 통합 검증·포트폴리오 근거 정리

- [ ] pytest/ruff와 Spring 신규·관련 테스트를 실행하고 결과를 기록한다. SQL은 로컬 pgvector 환경에서 확인한다.
- [ ] 문화 설명, 조건부 추천, 모호 조건, 미존재 ID, 비활성화, catalog outage, LLM outage, 호출 한도를 HTTP부터 최종 응답까지 검증한다.
- [ ] Spring→FastAPI→Spring catalog 대기 중 바깥 Spring이 DB connection을 보유하지 않는지 측정한다. legacy의 동일 문제까지 수정했다고 주장하지 않는다.
- [ ] catalog 변경 시 최종 재검증과 Decimal 가격 경계를 양쪽 언어로 확인한다.
- [ ] dataset/version/hash, graph 그림, 정상/실패 trace, 원본 결과, 평가 한계를 README/docs에 정리한다.
- [ ] 계획과 실제 변경 파일을 대조해 완료/미완료를 표시한다. 신규/기존 API 계약 차이도 재확인한다.

완료 후 설명할 경험은 ‘LangGraph StateGraph로 세 읽기 도구를 동적으로 선택·반복하는 서비스 구현’, ‘조건 검증과 실패 종료’, ‘동일 데이터셋 반복 실행과 LLM/사람 채점 대조’다. 성능 개선 수치는 실제 측정 후에만 작성한다.

## 구현 순서와 첫 검토 단위

Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8.
첫 구현 단위는 Task 1과 Task 2의 계약·catalog다. 모델 연결 전에 조건을 지키는 실제 데이터를 조회할 수 있는지 검증한다.
현재 문서의 체크박스는 앞으로 할 일이며 구현 완료 표시가 아니다.

## 참고 자료와 읽는 순서

1. [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) — State/Node/Edge와 반복 실행.
2. [Custom RAG Agent](https://docs.langchain.com/oss/python/langgraph/agentic-rag) — 기존 검색을 tool로 교체하는 예제.
3. [Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents) — 고정 흐름과 동적 도구 선택의 차이.
4. [Evaluation repetitions](https://docs.langchain.com/langsmith/repetition) — 반복·집계 개념. v1은 로컬 runner로 구현한다.
5. [Munder Difflin setup guide](https://lazyowen.com/guides/munder-difflin-ai-office-setup) — 코딩 에이전트의 데스크톱 운영 안내. 서비스용 LangGraph 구현 학습 자료와 용도가 다르다.

## 계획 자체 검토

- [x] Python/Spring 조사 SHA 고정.
- [x] 기존 트랜잭션·timeout·인원 전달·가격 타입 차이 반영.
- [x] 기존 RAG와 신규 agent API 분리.
- [x] 규칙 평가와 자유문 답변 평가 구분.
- [x] 비교 조건·데이터 분할·실패 분모·cache 기준 명시.
- [x] 예약 좌석과 영구 대화 상태를 미지원으로 명시.
- [x] bplus 제외.

## 2026-10-12 첫 구현 범위 보정

- 이번 요청은 Task 1(계약·평가 데이터)과 Task 2(Spring 조회 도구)까지 구현·커밋·PR한다. Task 3~8은 후속이다.
- 현재 저장소에는 실서비스 문화 DB snapshot이 없다. Task 1의 문화 데이터는 합성 계약/회귀 seed로 만들고 synthetic provenance를 표시한다. 실제 heritage ID와 사람이 확인한 정답 snapshot은 Task 6의 live 평가 전에 수집한다. 합성 자료의 통과를 실제 RAG 품질로 보고하지 않는다.
- Task 1은 catalog 계약과 에이전트 입력/출력 DTO, 고정 fixture, dataset 검증을 제공한다. 모델/그래프/API 실행은 추가하지 않는다.
- Spring 조회 도구의 모든 hard constraints는 기존 추천 경로와 분리한다. 기존 security 정책과 응답을 회귀 테스트한다.
- 계획 문서와 이번 구현 계약 문서는 두 저장소에 포함한다.
