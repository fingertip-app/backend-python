# ETL/Search Smoke Test

Use this after local data load and embedding generation to confirm pgvector
search returns reasonable results.

## Command

Vector-only DB check:

```bash
OPENAI_API_KEY=... UV_CACHE_DIR=.uv-cache uv run python scripts/smoke_test.py
```

Optional threshold:

```bash
SMOKE_SIMILARITY_THRESHOLD=0.25 UV_CACHE_DIR=.uv-cache uv run python scripts/smoke_test.py
```

API check after FastAPI is running:

```bash
RAG_API_BASE_URL=http://127.0.0.1:8000 \
INTERNAL_API_KEY=test-internal-key \
UV_CACHE_DIR=.uv-cache uv run python scripts/rag_api_smoke_test.py
```

The vector-only check confirms that embeddings were reloaded. The API check
confirms the actual `/api/v1/ai/explain` path, including lexical boost and
source extraction.

## Built-In Queries

Use these after the DB owner reloads `vector_documents` with the metadata-enriched
embedding text.

| Query | Expected signal | Why this matters |
| --- | --- | --- |
| `조선시대 궁중 자수에 대해 알려주세요` | `자수장` should appear in the top results or API sources. | Regression case: exact cultural keyword was previously outside the vector top-k. |
| `한산모시짜기에 대해 알려주세요` | `한산모시짜기` should appear. | Verifies exact heritage names survive retrieval. |
| `판소리 배우고 싶어요` | `판소리` should appear. | Verifies common user intent phrasing. |
| `매듭 공예가 뭐예요` | `매듭장` or a closely related craft result should appear. | Verifies category/content keyword boost. |
| `도자기 만드는 전통 기술` | Ceramic/pottery-related rows should appear. | Verifies broader semantic retrieval still works. |
| `우주여행 로켓 발사` | No strong cultural result is expected. | Negative smoke case for irrelevant queries. |

The positive cases should return related cultural rows when source data and
embeddings are loaded. The negative case may return no result or weak results
below the threshold.

## Pass Criteria

- Each positive query returns at least one obviously related row in the top 5.
- The `조선시대 궁중 자수에 대해 알려주세요` query includes `자수장` in the top
  results or `/api/v1/ai/explain` sources.
- The negative query does not produce a confident-looking unrelated cultural
  answer.
