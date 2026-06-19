# ETL/Search Smoke Test

Use this after local data load and embedding generation to confirm pgvector
search returns reasonable results.

## Command

```bash
OPENAI_API_KEY=... UV_CACHE_DIR=.uv-cache uv run python scripts/smoke_test.py
```

Optional threshold:

```bash
SMOKE_SIMILARITY_THRESHOLD=0.25 UV_CACHE_DIR=.uv-cache uv run python scripts/smoke_test.py
```

## Built-In Queries

- `도자기 만들기 체험`
- `판소리 배우기`
- `우주여행 로켓 발사`

The first two should return related cultural rows when data and embeddings are
loaded. The last query is a negative smoke case and may return no result.
