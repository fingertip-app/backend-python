# AI Testing Criteria

## Purpose

This document defines the minimum test criteria for the FastAPI AI endpoint,
the Spring FastAPI client, and the frontend AI search experience.

## FastAPI Test Criteria

Current reference files:

- `tests/test_ai_failures.py`
- `tests/test_internal_auth.py`

| # | Case | Expected result | Current coverage |
| ---: | --- | --- | --- |
| 1 | Normal response with valid internal API key | `200`, response includes `answer`, `sources`, `matchingKeywords`, `recommendedCategories` | `test_internal_auth.py::test_ai_explain_valid_key` |
| 2 | Missing internal API key header | `401`, `detail=Missing X-Internal-Api-Key header` | `test_ai_failures.py::test_ai_explain_missing_internal_key`; `test_internal_auth.py::test_ai_explain_missing_header` |
| 3 | Invalid internal API key | `403`, `detail=Invalid X-Internal-Api-Key` | `test_ai_failures.py::test_ai_explain_invalid_internal_key`; `test_internal_auth.py::test_ai_explain_invalid_key` |
| 4 | Request validation failure: empty query | `422` | `test_ai_failures.py::test_ai_explain_query_empty` |
| 5 | OpenAI API key not configured | `503`, `detail=OpenAI API is not configured` | `test_ai_failures.py::test_ai_explain_openai_key_not_set` |
| 6 | Embedding provider failure | `502`, `detail=Embedding provider request failed` | `test_ai_failures.py::test_ai_explain_embedding_failure` |
| 7 | Generation provider failure | `502`, `detail=Generation provider request failed` | `test_ai_failures.py::test_ai_explain_generation_failure` |
| 8 | Search miss / no source documents | `200`, `sources=[]`, empty matching arrays | `test_ai_failures.py::test_ai_explain_no_search_results` |
| 9 | Timeout or unexpected AI route exception | `503`, `detail=AI service unavailable` | `test_ai_failures.py::test_ai_explain_timeout_simulation` |
| 10 | Fallback behavior | Matching fallback returns `200`; unmatched fallback returns `503` | `test_ai_failures.py::test_ai_explain_fallback_enabled`; `test_ai_failures.py::test_ai_explain_fallback_enabled_without_matching_data` |

Additional authentication coverage:

| Case | Expected result | Current coverage |
| --- | --- | --- |
| Health endpoint without auth | `/health` returns `200` without internal API key | `test_internal_auth.py::test_health_without_auth` |
| FastAPI internal key not configured | `503`, internal auth configuration error | `test_internal_auth.py::test_ai_explain_rejects_unconfigured_internal_key` |

Status: `test_ai_failures.py` covers the requested 10 FastAPI cases. `test_internal_auth.py`
covers the required internal authentication cases and adds health/unconfigured-key checks.

## Spring Test Criteria

Spring tests should validate the client behavior around the FastAPI contract.
The expected reference test class is `FastApiClientTest.java`.

| # | Case | Expected result | Current coverage |
| ---: | --- | --- | --- |
| 1 | Normal FastAPI `200` response | Maps `answer`, `sources`, `matchingKeywords`, `recommendedCategories` into Spring response model | [TODO] Confirm in Spring repository |
| 2 | Search miss: FastAPI `200` with `sources=[]` | Returns no-result state without treating it as an error | [TODO] Confirm in Spring repository |
| 3 | FastAPI `401` | Maps to authentication/configuration failure; no retry | [TODO] Confirm in Spring repository |
| 4 | FastAPI `403` | Maps to security/configuration failure; no retry | [TODO] Confirm in Spring repository |
| 5 | FastAPI `503` configuration error | Maps to AI configuration or unavailable state according to Spring error model | [TODO] Confirm in Spring repository |
| 6 | FastAPI provider `502`, retry success | Retries once and returns successful mapped response | [TODO] Spring retry policy decision required |
| 7 | FastAPI provider `502`, retry failure | Returns AI unavailable after retry is exhausted | [TODO] Spring retry policy decision required |
| 8 | Connect timeout | Returns AI timeout response to app layer | [TODO] Confirm in Spring repository |
| 9 | Read timeout | Returns AI timeout response to app layer | [TODO] Confirm in Spring repository |

[TODO] Decide whether Spring implements a single retry for provider `502`. The
current internal API contract says this is planned but not implemented.

## Frontend Test Criteria

Frontend tests should validate the user-visible AI search states exposed by
Spring, not the internal FastAPI endpoint directly.

| # | Scenario | Expected UI behavior | Current coverage |
| ---: | --- | --- | --- |
| 1 | Normal AI search | Shows answer, source-backed context, and recommended experiences when available | [TODO] Confirm in frontend repository |
| 2 | Search miss | Shows no-result guidance without error styling | [TODO] Confirm in frontend repository |
| 3 | Timeout | Shows timeout-specific retry guidance | [TODO] Confirm in frontend repository |
| 4 | AI failure | Shows temporary failure state and does not expose internal error details | [TODO] Confirm in frontend repository |
| 5 | Fallback response | Shows fallback answer as a normal successful result or marks it according to product decision | [TODO] Product/UI decision required |
| 6 | Browser/network error | Shows network error state and allows retry | [TODO] Confirm in frontend repository |

## Decision Items

- [TODO] `matchingKeywords` count: 1-3 items or variable.
- [TODO] `recommendedCategories` count: 1-2 items or variable.
- [TODO] Locale support: `ko` only or `ko/en/ja`.
- [TODO] Spring provider `502` retry: implement one retry or keep no retry.
