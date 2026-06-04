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
  "matchingKeywords": ["매듭장"],
  "recommendedCategories": ["공예"]
}
```

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

FastAPI uses FastAPI's JSON error detail response for non-`200` failures:

```json
{
  "detail": "Error description"
}
```

| Situation | FastAPI HTTP | Spring handling |
| --- | ---: | --- |
| Missing internal API key header | `401` | Treat as server integration configuration failure; no retry |
| Invalid internal API key | `403` | Treat as server integration configuration failure; no retry |
| FastAPI internal key not configured | `503` | Deployment configuration failure; no retry |
| OpenAI API key not configured | `503` | AI unavailable; fallback may apply in FastAPI when enabled |
| OpenAI embedding request failed | `502` | AI unavailable; retry policy is Spring-owned |
| OpenAI generation request failed | `502` | AI unavailable; retry policy is Spring-owned |
| Empty/invalid request | `422` | Spring validates before calling; expose bad request |
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

Fallback is not used for `401`, `403`, `422`, or successful `200` no-result
responses. If fallback is enabled but no demo entry matches, FastAPI returns
`503` with `{"detail": "AI service unavailable"}`.

The current Spring `FastApiClient` maps `401`/`403` to `AI_CONFIG_ERROR`,
`502`/`503` to `AI_UNAVAILABLE`, and network/read timeouts to `AI_TIMEOUT`.
The planned provider `502` single retry is not implemented in the current
Spring client as of this document update.

## Timeout Policy

| Setting | Initial MVP Value |
| --- | ---: |
| Spring to FastAPI connect timeout | `1,000 ms` |
| Spring to FastAPI read timeout | `15,000 ms` |
| Automatic retry | none in current Spring client; provider `502` single retry is planned |

Timeout values are initial limits and should be revisited after seeded RAG
queries are measured.
