# Spring - FastAPI Internal API Contract

## Scope

FastAPI exposes AI-only internal APIs. Spring Boot is the only server called by
the app and is responsible for combining AI matching hints with experience
data.

## Authentication

All `/api/v1/ai/*` requests require the server-to-server header:

```http
X-Internal-Api-Key: ${INTERNAL_API_KEY}
```

- FastAPI must not be exposed as an app-facing API.
- Spring and FastAPI communicate on an internal network.
- `INTERNAL_API_KEY` is injected as a deployment secret and is never committed.
- `GET /health` remains unauthenticated for health checks.

## Explain Culture

```http
POST /api/v1/ai/explain
Content-Type: application/json
X-Internal-Api-Key: ${INTERNAL_API_KEY}
```

Request:

```json
{
  "query": "드라마에 나온 매듭은 어떤 전통문화예요?",
  "locale": "ko"
}
```

Fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `query` | string | yes | Non-empty user question |
| `locale` | string | no | Response locale; defaults to `ko` |

FastAPI response (`200`):

```json
{
  "answer": "매듭은 실을 엮어 장식과 실용에 활용해 온 전통 공예입니다.",
  "sources": [
    {
      "id": 7,
      "name": "매듭장",
      "source": "국가유산포털",
      "category": "공예"
    }
  ],
  "matchingKeywords": ["전통매듭", "체험형", "소품만들기"],
  "recommendedCategories": ["체험형", "소품만들기"]
}
```

`matchingKeywords`와 `recommendedCategories`는 문화유산 이름·분류를 앱의 체험 태그로 매핑한 후보입니다. 현재 매퍼는 일반 태그도 포함하며, 두 배열의 순서는 보장하지 않습니다.

When no source document is retrieved, FastAPI still responds with `200`, an
explanatory `answer`, and empty source/matching arrays.

## Spring App Response

Spring maps `matchingKeywords` and `recommendedCategories` to its owned
experience data. The app never receives an internal FastAPI URL or key.

```json
{
  "answer": "매듭은 실을 엮어 장식과 실용에 활용해 온 전통 공예입니다.",
  "sources": [
    {
      "id": 7,
      "name": "매듭장",
      "source": "국가유산포털",
      "category": "공예"
    }
  ],
  "recommendedExperiences": []
}
```

The client skeleton may return an empty `recommendedExperiences` list until
Spring-side experience matching is implemented.

## Failure Contract

FastAPI uses a standard `detail` response for most non-`200` failures. Request
validation has a dedicated `400` response:

```json
{
  "success": false,
  "message": "AI query validation failed",
  "errorCode": "INVALID_REQUEST",
  "details": [
    {"loc": ["body", "query"], "msg": "String should have at least 1 character", "type": "string_too_short"}
  ]
}
```

| Situation | FastAPI HTTP | Spring handling |
| --- | ---: | --- |
| Missing internal API key header | `401` | Treat as server integration configuration failure; no retry |
| Invalid internal API key | `403` | Treat as server integration configuration failure; no retry |
| FastAPI internal key not configured | `503` | Deployment configuration failure; no retry |
| OpenAI API key not configured | `503` | AI unavailable; fallback may apply in FastAPI when enabled |
| OpenAI embedding request failed | `502` | Spring retries provider `502` once, then returns AI unavailable if retry fails |
| OpenAI generation request failed | `502` | Spring retries provider `502` once, then returns AI unavailable if retry fails |
| Empty/invalid request | `400` | Spring rejects as an invalid request; no retry |
| FastAPI network timeout | no response | Return AI timeout response to app |

Structured AI error codes are a follow-up improvement; Spring must not parse
the current `detail` message to distinguish configuration causes.

## Demo Fallback Contract

FastAPI can serve file-based fallback responses when:

- `AI_FALLBACK_ENABLED=true`
- the failure is an AI/provider failure (`502` or OpenAI configuration `503`)
  or an unexpected AI route exception
- `AI_FALLBACK_DATA_PATH` contains a matching demo entry

Fallback responses use the same `200` response schema as normal explain
responses:

```json
{
  "answer": "판소리는 한 사람의 소리꾼이 고수의 북 장단에 맞춰...",
  "sources": [
    {
      "id": 101,
      "name": "판소리",
      "source": "국가무형유산 공개 자료",
      "category": "음악"
    }
  ],
  "matchingKeywords": ["판소리", "소리꾼", "고수"],
  "recommendedCategories": ["음악", "공연"]
}
```

Fallback is not used for `400`, `401`, `403`, or successful `200` no-result
responses. If fallback is enabled but no demo entry matches, FastAPI returns
`503` with `{"detail": "AI service unavailable"}`.

The current Spring `FastApiClient` maps `401`/`403` to `AI_CONFIG_ERROR`,
provider `502` to a single retry before `AI_UNAVAILABLE`, `503` to
`AI_UNAVAILABLE` without retry, and network/read timeouts to `AI_TIMEOUT`.

## Timeout Policy

| Setting | Initial MVP Value |
| --- | ---: |
| Spring to FastAPI connect timeout | `1,000 ms` |
| Spring to FastAPI read timeout | `15,000 ms` |
| Automatic retry | provider `502` only, once, after `500 ms`; `503` is not retried |

Timeout values are initial limits and should be revisited after seeded RAG
queries are measured.
