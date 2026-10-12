# 장인과 하루 — 다른 노트북에서 이어가기

작성일: 2026-10-12 (Asia/Seoul)

> GitHub 게시 안내 (2026-10-12): 구현을 재개하지 않고 중지 시점의 커밋과 이 인수인계 자료를 `feat/langgraph-catalog-contracts`에 게시했다. 아래의 “아직 push/PR 없음”과 HEAD는 **중지 당시 snapshot**을 설명한다. ZIP도 그 snapshot 그대로이며, 게시 커밋에는 인수인계 MD/ZIP만 추가된다. PR 생성·merge·배포는 하지 않는다.
>
> 다른 노트북에서는 두 저장소를 `git clone --branch feat/langgraph-catalog-contracts <저장소 URL>`로 받아도 된다. 이 폴더의 ZIP을 저장소 밖에 풀고 `work-in-progress/*.patch`를 각각 `git apply --check` 후 `git apply`하고, 대응하는 `new-files/.`를 저장소에 복사하면 미커밋 작업까지 복원된다. 이 방법은 bundle fetch가 필요 없다. 아래 bundle 방식도 중지 당시 HEAD를 복원하는 별도 방법으로 유효하다.

## 1. 중지 상태와 요청 범위

사용자가 구현 중지와 인수인계 파일 작성을 요청했다. 구현 에이전트를 중지했고 실행 중인 관련 테스트 프로세스도 없는 것을 확인했다. 이후 작업은 이 인수인계 자료의 저장·복원 확인에 한정했다.

**아직 push 및 PR 생성은 하지 않았다.** 아래 커밋은 원래 노트북에만 있다. 다른 노트북에서 GitHub 저장소만 clone하면 이번 작업이 나타나지 않으므로, 동봉한 bundle과 미커밋 파일을 함께 복원해야 한다.

원래 요청은 다음과 같다.

> 장인과 하루에 기존 기능을 유지하면서 별도 브랜치에서 계약·평가 데이터와 Spring 조회 도구부터 구현한다. 계획 문서도 모두 포함하고, 작업별로 커밋하고 PR을 올린다.

- 이번 구현 범위는 전체 8단계 계획 중 **Task 1과 Task 2**다.
- 대상은 `fingertip-app/backend-python`, `fingertip-app/backend` 두 저장소다. **bplus는 제외**한다.
- 브랜치 이름에 `codex/`를 붙이지 않는다. 두 저장소 모두 `feat/langgraph-catalog-contracts`를 사용한다.
- PR base는 양쪽 모두 `develop`이다. 기존 요청은 각 저장소 PR 생성까지였으며 merge·배포는 포함하지 않는다.
- Task 1은 커밋됐지만 Spring 교차 계약 리뷰의 수정이 끝나지 않았다. **Task 2는 시작하지 않았다.** LangGraph 그래프·모델 호출·반복 평가 실행기도 아직 구현하지 않았다.

## 2. 저장소·커밋

| 항목 | Python | Spring |
|---|---|---|
| GitHub | https://github.com/fingertip-app/backend-python.git | https://github.com/fingertip-app/backend.git |
| 기준 develop | `cf9cd219b8baabcbc8079dbe6c30cdc04e5e126e` | `58b712a69277c2c0e3887f51bc20c861a6706f01` |
| 중지 시 HEAD | `8c22d88ced5d528938e6d0df7ca61c541ec92f75` | `1c9b183ef7e2569697a4ba3b7d2ab4d78c6064d5` |
| 원래 로컬 경로 | `/Users/yj/Desktop/Projects/janginharou/backend-python` | `/Users/yj/Desktop/Projects/janginharou/backend` |

Python의 작업 커밋:

1. `deb8626d1ce0a7e426d6e2d89fe5b0b1d456fca6` — 계획 문서 추가.
2. `335720e63050765575da679094663bbc94925a84` — 기존 구현에 맞게 오래된 회귀 테스트 기대값 보완. 기존 애플리케이션 동작 수정 없음.
3. `a8bd0ab78f21eeb34845f2e15166feaf4d06af43` — 신규 계약·합성 평가 seed.
4. `8c22d88ced5d528938e6d0df7ca61c541ec92f75` — JSON 금액 정밀도 및 공개 schema 보완.

Spring의 작업 커밋:

1. `a3441e39665818405ab8affb4a5e5da5cbb8784c` — 계획 문서 추가.
2. `9d411060e10c4fbb283e8acdc9023966be8e53f9` — 기존 `ReviewServiceTest`의 누락된 `ArtisanRepository` import 추가.
3. `1c9b183ef7e2569697a4ba3b7d2ab4d78c6064d5` — 신규 agent DTO 및 공통 계약 예제·테스트.

두 저장소에서 `develop`은 중지 전 확인 시 기준 SHA와 같았다. 재개·게시 시에는 다시 fetch하고 차이가 있으면 재검토한다. 커밋 기록을 다시 만들거나 기존 작업을 덮어쓰지 않는다.

## 3. 복원 방법

이 MD와 같은 폴더의 자료가 들어 있는 ZIP 전체를 다른 노트북으로 옮겨 압축을 푼다. private 저장소를 clone할 GitHub 인증이 필요하다. bundle은 **증분 bundle**로, 위의 기준 develop 커밋을 전제로 한다. 아래처럼 저장소를 정상 clone한 뒤 가져온다. 기존 변경이 없는 새 폴더에서 실행한다.

```bash
# 압축을 푼 인수인계 폴더에서 시작한다.
HANDOFF_DIR="$(pwd)"
mkdir -p ../janginharou-resume
cd ../janginharou-resume

git clone --branch develop https://github.com/fingertip-app/backend-python.git backend-python
git clone --branch develop https://github.com/fingertip-app/backend.git backend

git -C backend-python bundle verify "$HANDOFF_DIR/bundles/backend-python.bundle"
git -C backend bundle verify "$HANDOFF_DIR/bundles/backend.bundle"

git -C backend-python fetch "$HANDOFF_DIR/bundles/backend-python.bundle" \
  refs/heads/feat/langgraph-catalog-contracts:refs/heads/feat/langgraph-catalog-contracts
git -C backend fetch "$HANDOFF_DIR/bundles/backend.bundle" \
  refs/heads/feat/langgraph-catalog-contracts:refs/heads/feat/langgraph-catalog-contracts

git -C backend-python switch feat/langgraph-catalog-contracts
git -C backend switch feat/langgraph-catalog-contracts

git -C backend-python apply --check "$HANDOFF_DIR/work-in-progress/backend-python.patch"
git -C backend apply --check "$HANDOFF_DIR/work-in-progress/backend.patch"
git -C backend-python apply "$HANDOFF_DIR/work-in-progress/backend-python.patch"
git -C backend apply "$HANDOFF_DIR/work-in-progress/backend.patch"

cp -R "$HANDOFF_DIR/work-in-progress/backend-python/new-files/." backend-python/
cp -R "$HANDOFF_DIR/work-in-progress/backend/new-files/." backend/

git -C backend-python rev-parse HEAD
git -C backend rev-parse HEAD
git -C backend-python status --short
git -C backend status --short
```

HEAD는 위 표와 같아야 한다. 변경 목록은 `context/backend-python-git-status.txt`, `context/backend-git-status.txt`와 대조한다. 명령 하나가 실패하면 다음 명령을 계속 실행하지 말고 원인을 확인한다. `--depth 1` clone은 bundle의 선행 커밋이 없을 수 있으므로 사용하지 않는다.

MD만 옮기는 경우에는 이력·코드를 복원할 수 없다. ZIP에 포함된 bundle, patch, 신규 파일도 함께 옮겨야 한다. `.venv`, JDK, Gradle 캐시, 실제 비밀 환경변수는 포함하지 않았다.

## 4. 구현된 내용

### Python

- `app/schemas/agent.py`: 요청·제약조건·draft·최종 응답·문화 검색·catalog 검색/응답의 엄격한 계약.
- `app/evaluation/dataset.py`: seed 읽기, provenance·참조 무결성·corpus SHA-256·ID 중복·dev/test group 누출 검증.
- `evaluation/seeds/v1/`: 문화 설명 20개, 추천 20개, 합성 catalog 12개, 합성 문화 corpus 5개. 각 평가 세트는 dev 10/test 10.
- `docs/contracts/agent-v1/`: validation/serialization JSON Schema와 공통 유효·실패·Decimal wire 예제.
- `tests/agent/`: 계약, 데이터셋, 기존 explain/recommendation 응답 보존 테스트.

금액은 JSON 숫자 또는 정해진 형식의 문자열로 받아 문자열로 출력한다. `parse_contract_json(raw)`가 `json.loads(parse_float=Decimal)`을 사용한다. **향후 FastAPI agent route는 raw `request.body()`를 이 파서에 전달해야 한다.** 이미 float로 읽힌 dict에서는 잃은 정밀도를 복구할 수 없다. 숫자 JSON의 지수 표현은 가능하고, 문자열은 unsigned 일반 십진수 표기만 허용한다. 유효 소수 자릿수는 2자리이며 뒤쪽 0은 허용한다. 임의 금액 상한은 추가하지 않았다.

### Spring

- 신규 DTO 패키지: `com.janginharou.domain.ai.dto.agent`.
- `WireValues`의 DTO별 deserializer/serializer로 엄격한 타입과 BigDecimal 문자열 출력을 적용했다.
- omitted 기본값과 explicit null을 구별하기 위해 request/search/constraints는 초기값을 가진 POJO다. response는 record를 사용한다.
- `AgentContractTest` 및 `src/test/resources/contracts/agent-v1/` 공통 예제.
- 글로벌 Jackson 설정과 기존 API·서비스·저장소는 변경하지 않았다. 새 catalog controller/service/filter도 아직 없다.

공통 규칙: locale `ko`, region `SEOUL/GYEONGGI/INCHEON/BUSAN/JEJU`, headCount 1~20/기본 1, search limit 1~10/기본 5, queryTerms 1~5개·trim 후 항목당 1~50자. 신규 DTO는 unknown field를 거부한다. catalog의 핵심 필드는 id/title/descriptionExcerpt/tags/priceKrw/maxParticipants/regionCode/isActive이며 detail에는 description이 추가된다.

**평가 seed는 합성 데이터이며 `humanReviewed=false`다.** 실제 국가유산 DB snapshot과 사람의 사실 검증은 아직 없다. 현재 결과를 실제 모델 품질·개선률·LangGraph 경험으로 표현하면 안 된다. 실제 snapshot 확보는 Task 6 이전의 전제다. `maxParticipants`는 프로그램 정원이며 남은 예약 좌석이 아니다.

## 5. 재개할 첫 작업 — Task 1 수정 루프

Python의 앞선 Important 지적 두 건은 `8c22d88`에서 해결됐고 재리뷰가 통과했다. Spring은 다음 두 Important 지적 때문에 아직 사양·품질 승인을 받지 못했다.

1. **Unicode 공백:** Java `String.strip()`/`@NotBlank`와 Python/Pydantic의 trim 규칙이 다르다. NBSP(U+00A0)만 있는 query가 Spring에서는 유효하고 Python에서는 실패한다. NBSP padding도 Spring에 남는다. scoped `WireValues`의 정규화 규칙을 Python에 맞추고 queryTerms 등 같은 문자열 deserializer 사용처를 검증한다. Character.isWhitespace/isSpaceChar와 NEL(U+0085) 등을 고려하되 공유 fixture로 실제 일치를 확인한다.
2. **문자 길이:** Java `@Size`는 UTF-16 단위를 세지만 Python/JSON Schema는 code point를 센다. emoji 300개 query, emoji 30개 queryTerm은 Python에서 유효하고 Spring에서 실패한다. excerpt 등 길이 제한이 있는 모든 문자열도 같은 문제다. 문자열용 scoped code-point validator로 맞추고 목록 크기의 기존 `@Size`는 유지한다.
3. **Minor schema 끝의 줄바꿈:** 기존 금액 regex의 `$`는 JSON Schema에서 trailing LF를 허용하지만 runtime `fullmatch`는 거부한다. 이 수정도 함께 착수했다. 끝 조건을 JS/JSON Schema에서 호환되는 `(?![\s\S])`로 바꾸는 중이다. 완성·재검증은 아직 안 됐다.

상세 리뷰는 `context/sdd/task-1-spring-review.md`, `task-1-python-rereview.md`에 있다.

중지 시 **미커밋 상태**:

- Python: tracked 12개 수정 + `docs/contracts/agent-v1/unicode-wire-examples.json` 신규 1개. 금액 regex와 관련 schema, README/Decimal 예제, Unicode/줄바꿈 테스트를 수정했다.
- Spring: `AgentContractTest.java` 수정 + test resources의 `unicode-wire-examples.json` 신규 1개. **Spring production Unicode 수정은 아직 없다.**
- 이 WIP는 테스트 통과나 리뷰 완료가 보장되지 않는다. 마지막 green 결과는 WIP 이전의 커밋을 대상으로 한다.
- Spring의 docs와 test resources 및 Python docs는 **WIP 상태에서 아직 완전히 동기화되지 않았다.** 수정 완료 후 예제·schema를 byte 단위로 대조하고 정리한다.

이미 커밋된 Task 1을 처음부터 재구현하지 않는다. WIP와 리뷰를 읽고 실패 재현 → scoped 수정 → 테스트 → 별도 수정 커밋 → scoped 재리뷰 순서로 마친다. 커밋은 작업별로 남기고 기존 이력을 squash/reset하지 않는다.

## 6. 그다음 작업 — Task 2 Spring 조회 도구

상세 요구사항은 `context/sdd/task-2-brief.md`가 우선이다. Task 1의 양쪽 계약 리뷰를 완료한 뒤 진행한다.

- POST `/internal/ai/experiences/search`: `{queryTerms,constraints,limit}`.
- GET `/internal/ai/experiences/{id}`: regionCode/maxPriceKrw/headCount query 제약.
- `ApiResponse(success,message,data,errorCode)` envelope. detail 미존재·비활성·조건 불일치 404, search 빈 목록 200.
- `X-AI-Service-Key` 인증을 정확한 메서드·경로에만 적용하고 `ROLE_AI_SERVICE` 설정. 키 미설정 503/헤더 누락 401/불일치 403. 기존 JWT 및 공개 경로 유지. 새 필터의 servlet 중복 등록 방지.
- active/가격/정원/지역을 **SQL limit 전에 적용**한다. 전체 목록을 읽고 메모리에서 거르는 방식은 사용하지 않는다.
- title/description/tags 중 하나 이상의 검색어 일치. 제목/태그 점수 후 ID 안정 정렬. 태그 join 중복 방지. `%`, `_`, 백슬래시는 LIKE literal로 처리.
- supported 시·도 접두어로 주소 정규화. 지역 필터가 있을 때 null/미지원 주소 제외.
- 짧은 readOnly transaction 안에서 lazy tags 접근과 DTO 변환까지 마치고 연결 반환. AI 서비스 재호출 금지.
- query timeout 2초는 catalog query에 한정. 기존 글로벌 Hikari pool 설정은 변경하지 않는다. connection acquisition 관련 실험 설정은 별도 환경으로 취급한다.
- 실제 JPA/H2 integration test로 50000/50000.01 금액 경계, 정원 3, null 주소, 필터-before-limit, 정렬·중복·wildcard를 검증한다. PostgreSQL 전용 문법을 쓰면 실제 PostgreSQL 검증이 필요하다.
- 신규 내부 API의 malformed JSON/unknown field/타입 오류와 잘못된 GET constraints는 400 envelope로 처리한다. 기존 generic `GlobalExceptionHandler`는 JSON decode 예외를 500으로 처리할 수 있어 **신규 컨트롤러에 한정된 처리**가 필요하다. 기존 API의 오류 동작은 유지한다.
- AI_SERVICE_KEY 환경변수 및 기본 미설정 503을 runbook에 기록하되 비밀 값은 저장하지 않는다.

참고 기존 코드: Spring `Experience.price`는 BigDecimal precision 10/scale 2, maxParticipants는 Integer, locationAddress는 문자열, tags는 ElementCollection, isActive는 boolean이다. 기존 ExperienceRepository 메서드와 RecommendationService 동작은 유지한다.

## 7. 검증 결과와 실행 환경

**커밋 상태에서 검증한 결과**:

- Python `8c22d88`: `python -m pytest tests -q` **128 passed**. 별도의 깨끗한 checkout에서 Python **3.11.15**로 의존성을 frozen 설치한 후 같은 128개 통과, 신규 영역 Ruff 검사도 통과했다. 증거는 `verification/`에 있다.
- Spring `1c9b183`: JDK 17 전체 Gradle test **82 tests / 0 failures / 0 errors**. 기존 76개 + 계약 테스트 6개. Spring의 최종 깨끗한 checkout 검증은 아직 하지 않았다.
- bare `pytest -q`는 historical `scripts/test_*`까지 수집해 live DB/DATABASE_URL 없이 collection 오류가 난다. offline 회귀 검증은 `python -m pytest tests -q`다. live DB 스크립트까지 통과했다고 주장하지 않는다.
- Docker daemon이 없어 실제 PostgreSQL 실험은 수행하지 않았다. 기존/신규 모델 공급자 호출과 실제 AI 품질 평가도 수행하지 않았다.

다른 노트북에서는 Python 3.11 이상, uv, JDK 17, Git/GitHub 인증을 준비한다.

```bash
# Python 저장소에서
uv sync --python 3.11 --extra dev --frozen
uv run --frozen --extra dev python -m pytest tests -q
uv run --frozen --extra dev ruff check app/schemas/agent.py app/evaluation tests/agent

# Spring 저장소에서; 해당 노트북의 JDK 17 JAVA_HOME을 사용한다.
./gradlew test --no-daemon
./gradlew test --tests '*AgentContractTest' --no-daemon
# Task 2 구현 후
./gradlew test --tests '*InternalAiCatalog*' --tests '*AiServiceKey*' --no-daemon
```

원래 노트북의 임시 JDK/캐시 경로는 이식하면 안 된다: `/private/tmp/janginharou-tools/jdk-17.0.20.1+1/Contents/Home`, `/private/tmp/janginharou-gradle`, `/private/tmp/janginharou-tools/python`, `/private/tmp/janginharou-uv-cache`.

## 8. 문서·리뷰·게시 절차

- 전체 계획은 **양쪽 저장소에 이미 커밋**된 `docs/superpowers/plans/2026-10-12-langgraph-agent-evaluation.md`이며 `context/`에도 복사했다.
- `context/sdd/`: Task 1/2 brief, 구현 보고서, 리뷰·재리뷰, 진행 ledger, review diff package. 중간의 `Final git status: clean` 문장은 WIP 이전 시점의 기록이므로 `snapshot.json`과 중지 시 변경 목록이 최신이다.
- `context/spring-review-packages/`: Spring 계약 review package.
- `context/snapshot.json`: 실제 중지 시 경로·HEAD·base·브랜치·변경 파일·커밋 목록.
- `verification/`: 이전 Python clean-checkout 검증 manifest/receipt/log. WIP나 향후 커밋을 검증한 증거로 재사용하지 않는다. receipt 안의 기존 절대 경로는 역사적 기록이다.

이 세션은 subagent-driven-development 방식으로 작업했다. 구현 에이전트는 한 번에 하나, 각 작업 후 spec+quality review, 마지막에 양쪽 브랜치 전체 review를 거친다. Task 1 수정 루프 후 Task 2에 새 구현 담당을 배정한다. 코드 리뷰의 Important 지적을 남긴 채 다음 단계의 완료를 선언하지 않는다.

Task 1/2가 완료되면 두 저장소의 최종 diff를 요구사항과 대조하고 깨끗한 checkout에서 최종 커밋을 검증한다. 로컬 ignored 파일·비밀 환경변수를 복사해 통과시키지 않는다. 새 HEAD/base에 맞춰 게시 검증 증거를 새로 만든다. 이후 각 브랜치를 push하고 **develop 대상 PR 두 개**를 생성한다. Codex에서는 만든 PR마다 `attach_artifact`를 호출한다. 원격 head SHA·base·전체 파일 목록이 검증한 내용과 같은지 확인한다. 다른 작업 혼입·누락 여부도 확인한다.

최초 문서 커밋 때 guard checks가 빈 배열이라 capture가 실패했으나 당시 shell이 중단되지 않아 커밋이 진행된 이력이 있다. 이후 전체 diff를 포함한 Python 최종 capture/head/clean 검증은 통과했다. Spring도 게시 전에 전체 문서·모든 커밋을 포함해 새 검증을 해야 한다. 앞으로 guard/commit 스크립트는 `set -e` 또는 subprocess check=True로 실패 시 중단한다.

원래 노트북의 게시 guard 스킬 경로: `/Users/yj/.codex/skills/pr-publication-guard/SKILL.md` 및 `scripts/pr_guard.py`. 다른 노트북에는 없을 수 있다. 기존 절대 경로를 그대로 실행하지 말고 설치 여부를 확인하며, 스킬이 없다면 같은 단계의 파일·커밋·clean checkout·원격 PR 대조를 수행한다.

PR 본문은 한국어로 `## 문제 상황`, `## 해결 방법` 아래 간단한 bullet을 사용한다. 검증 결과와 합성 seed/미구현 graph/evaluation runner 범위를 명확히 적는다. 실제 LangGraph·반복 평가 경험을 확보하는 작업은 다음 Task 3~8이며 이번 PR 범위와 구별한다.

## 9. 새 세션에 전달할 요청

> 이 인수인계 MD와 동봉 자료를 읽고 장인과 하루 작업을 이어가줘. bplus는 제외하고 기존 API를 유지해줘. 먼저 bundle과 WIP를 새 폴더에 복원해서 HEAD·변경 목록을 확인해. 이미 커밋한 Task 1을 다시 만들지 말고 Spring Unicode 공백/code-point 길이와 공유 schema 줄바꿈 문제를 마무리하고 재리뷰해. 그다음 task-2-brief.md대로 Spring 읽기 전용 catalog API를 구현해. 이번 범위는 Task 1/2이며 LangGraph 실행과 평가 runner는 아직 만들지 않아. 작업별로 커밋하고 계획 문서도 포함해 양쪽 develop 대상 PR까지 올려줘. 브랜치명에 codex/를 붙이지 말고, 최종 clean-checkout 테스트와 원격 PR 파일·SHA 대조도 해줘.
