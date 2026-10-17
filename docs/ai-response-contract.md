# AI Response Contract

## Scope

This document defines the response contract for the internal FastAPI endpoint:

```http
POST /api/v1/ai/explain
Content-Type: application/json
X-Internal-Api-Key: ${INTERNAL_API_KEY}
```

Spring is the only intended caller. The app frontend must not call this
FastAPI endpoint directly.

## Request

```json
{
  "query": "드라마에 나온 매듭은 어떤 전통문화예요?",
  "locale": "ko"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `query` | string | yes | Non-empty user question. Empty strings are rejected with `422`. |
| `locale` | string | no | Response locale. Defaults to `ko`. Current MVP scope is `ko`; `en/ja` support is a pending frontend decision. |

## Normal Response: 200 OK

FastAPI returns `200 OK` when it can produce an AI explanation and at least one
source document is available.

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

## No Search Results: 200 OK

Search misses are not treated as transport or provider failures. FastAPI still
returns `200 OK`, with an explanatory `answer` and empty matching arrays.

```json
{
  "answer": "관련 문화유산 자료를 찾지 못했습니다. 질문을 더 구체적으로 입력해 주세요.",
  "sources": [],
  "matchingKeywords": [],
  "recommendedCategories": []
}
```

Spring and frontend clients must distinguish this case by `sources=[]`, not by
HTTP status.

## Fallback Response: 200 OK

When fallback is enabled and a matching fallback entry exists, FastAPI returns
the same `200 OK` schema as a normal response.

```json
{
  "answer": "판소리는 한 사람의 소리꾼이 고수의 북 장단에 맞춰 이야기를 노래로 풀어내는 전통 공연 예술입니다.",
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
responses. If fallback is enabled but no matching fallback data exists, FastAPI
returns `503`.

## Fallback Policy

| Situation | Use fallback | Reason |
| --- | --- | --- |
| Normal response | No | Use actual search/generation result. |
| No search results | No | Normal `200` no-source response. |
| `401` | No | Server-to-server authentication configuration issue. |
| `403` | No | Server-to-server security configuration issue. |
| `422` | No | Request validation failure. |
| `502` | Possible | Protect demo flow during OpenAI provider failure. |
| `503` | Possible | Protect demo flow during AI configuration/service failure. |
| Timeout | Possible | Protect demo stability. |

## Error Responses

FastAPI uses the default JSON error shape for non-`200` responses:

```json
{
  "detail": "Error description"
}
```

| HTTP status | Situation | Current `detail` example | Retry | Fallback |
| ---: | --- | --- | --- | --- |
| `401` | Missing `X-Internal-Api-Key` header | `Missing X-Internal-Api-Key header` | No | No |
| `403` | Invalid `X-Internal-Api-Key` | `Invalid X-Internal-Api-Key` | No | No |
| `422` | Request validation failure, including empty `query` | FastAPI validation error array | No | No |
| `502` | OpenAI embedding request failed | `Embedding provider request failed` | Spring-owned policy | Yes, when enabled and matched |
| `502` | OpenAI generation request failed | `Generation provider request failed` | Spring-owned policy | Yes, when enabled and matched |
| `503` | FastAPI internal API key not configured | `Internal API authentication is not configured` | No | No |
| `503` | OpenAI API key not configured | `OpenAI API is not configured` | No | Yes, when enabled and matched |
| `503` | Unexpected AI route error or timeout simulation | `AI service unavailable` | No | Yes, when enabled and matched |

Structured AI error codes are not part of the current contract. Spring must not
depend on parsing the free-form `detail` message beyond coarse status handling.

## ⚠️ Spring Integration Notes

- Spring `FastApiClient` must not parse the FastAPI error response `detail`
  string.
- Spring must distinguish these cases by HTTP status code only:
  - `401` -> authentication configuration issue
  - `403` -> security configuration issue
  - `502` -> provider failure (retry candidate)
  - `503` -> service unavailable (no retry)
- FastAPI error messages may change without breaking Spring behavior.

## Field Specification

| Field | Type | Required | Description | Sample |
| --- | --- | --- | --- | --- |
| `answer` | string | yes | User-facing explanation or no-result guidance. Must not be empty for successful responses. | `매듭은 전통 공예입니다.` |
| `sources` | array of `Source` | yes | Source documents used for the answer. Empty array means no matching source was found. | See `Source` below. |
| `matchingKeywords` | array of string | yes | Heritage item names or terms matched from source documents. Empty on search miss. Current count is variable; 1-3 item cap is pending decision. | `["매듭장"]` |
| `recommendedCategories` | array of string | yes | Culture categories Spring can use to map experiences. Empty on search miss. Current count is variable; 1-2 item cap is pending decision. | `["공예"]` |

### Source

| Field | Type | Required | Description | Sample |
| --- | --- | --- | --- | --- |
| `id` | integer | yes | FastAPI heritage item identifier. | `7` |
| `name` | string | yes | Heritage item name. | `매듭장` |
| `source` | string | yes | Source dataset or publisher name. | `국가유산포털` |
| `category` | string or null | yes | Optional heritage category. | `공예` |
