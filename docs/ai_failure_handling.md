# AI Failure Handling and Demo Fallback Guide

## Purpose

The AI explain API must keep the 6/28 demo usable even when OpenAI is
unavailable. The fallback is a demo safety path, not a production knowledge
source.

## Runtime Modes

| Environment | Required settings | Behavior |
| --- | --- | --- |
| Local demo | `AI_FALLBACK_ENABLED=true`, `OPENAI_API_KEY` empty or dummy | Known demo queries return file-based fallback responses when AI fails |
| Demo | `AI_FALLBACK_ENABLED=true`, valid `OPENAI_API_KEY` preferred | Normal RAG runs first; fallback is used only after AI/service failure |
| Production | `AI_FALLBACK_ENABLED=false`, valid `OPENAI_API_KEY` required | Provider failures return errors; fallback is disabled |

## FastAPI Fallback Settings

```bash
AI_FALLBACK_ENABLED=true
AI_FALLBACK_DATA_PATH=app/data/ai_fallback_responses.json
```

The fallback file is loaded by `app/services/ai/fallback_service.py`.
Relative paths are resolved from the FastAPI process working directory.

## Fallback Triggers

Fallback is attempted only when `AI_FALLBACK_ENABLED=true` and one of these
AI-layer failures happens:

| Failure | Normal status | Fallback behavior |
| --- | ---: | --- |
| OpenAI API key missing | `503` | Return matching fallback if available |
| Embedding provider failure | `502` | Return matching fallback if available |
| Generation provider failure | `502` | Return matching fallback if available |
| Unexpected AI route exception or timeout simulation | `503` | Return matching fallback if available |

Fallback is not used for request/auth failures:

| Failure | Status | Reason |
| --- | ---: | --- |
| Missing `X-Internal-Api-Key` | `401` | Spring/FastAPI integration error |
| Invalid `X-Internal-Api-Key` | `403` | Security error; no retry |
| Empty or invalid request body | `422` | Client request problem |
| Search returns no source documents | `200` | Valid AI response with empty sources |

If fallback is enabled but no fallback item matches the query, FastAPI returns:

```json
{
  "detail": "AI service unavailable"
}
```

## Demo Data

The default fallback file contains five realistic Korean traditional culture
entries:

| Key | Category |
| --- | --- |
| `판소리` | 음악, 공연 |
| `한복` | 복식, 생활문화 |
| `부채춤` | 무용, 공연 |
| `매듭` | 공예, 생활문화 |
| `탈춤` | 공연, 민속 |

Matching order:

1. Exact normalized query match.
2. Keyword containment match, for example `판소리 배우기` matches `판소리`.
3. No fallback response.

## 6/28 Demo Checklist

Before the demo:

```bash
export AI_FALLBACK_ENABLED=true
export AI_FALLBACK_DATA_PATH=app/data/ai_fallback_responses.json
```

Verify these requests through Spring or directly against FastAPI:

| Query | Expected behavior |
| --- | --- |
| `판소리` | Normal RAG answer if OpenAI works; fallback answer if it fails |
| `한복` | Fallback answer contains traditional clothing explanation |
| `부채춤` | Fallback answer contains Korean dance explanation |
| `존재하지 않는 종목` | No-source response or unavailable response; do not invent a fallback |

## Incident Steps

1. If OpenAI is slow or down, confirm `AI_FALLBACK_ENABLED=true` and restart
   FastAPI.
2. If FastAPI is down, Spring must show service-unavailable handling; FastAPI
   fallback cannot run while the process is unreachable.
3. If internal auth fails with `401` or `403`, fix deployment secrets. Do not
   retry or switch to fallback.
4. After the demo, set `AI_FALLBACK_ENABLED=false` before production use.
