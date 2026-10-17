# Demo Data Freeze

Freeze date: 2026-06-19

## Fallback Queries

The 6/28 demo fallback file is `app/data/ai_fallback_responses.json`.

Frozen keys:

- `판소리`
- `한복`
- `부채춤`
- `매듭`
- `탈춤`

## Verification

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python -m pytest tests/test_demo_fallback.py -q
```

Expected behavior:

- each frozen fallback response validates against the Spring explain schema
- keyword containment works, e.g. `판소리 배우기` matches `판소리`
- unmatched queries do not invent fallback data
