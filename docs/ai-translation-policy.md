# AI Translation Policy

## MVP Decision

Use the existing `locale` field on AI endpoints instead of adding a separate
translation endpoint for the MVP.

Supported MVP requests:

- `POST /api/v1/ai/explain` with `locale=ko`
- `POST /api/v1/ai/explain` with `locale=en`
- `POST /api/v1/ai/review-summary` with `locale=ko`
- `POST /api/v1/ai/review-summary` with `locale=en`

## Rationale

The Spring contract already forwards `locale`, and the FastAPI prompt can ask
the generation model to answer in the requested language while preserving the
same source list. A separate `/translate` endpoint would add another contract,
more error cases, and storage decisions that are not needed for the 6/28 MVP.

## Follow-Up

A separate translation API can be added after MVP if the product needs cached
translations, user-edited translations, or batch translation of stored content.
