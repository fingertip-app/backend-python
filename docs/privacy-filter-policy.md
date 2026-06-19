# AI Privacy Filter Policy

## MVP Decision

Before sending user-provided text to an AI provider, FastAPI masks:

- email addresses as `[email]`
- phone-like numbers as `[phone]`

This applies to:

- AI explain query text before embedding and generation
- review summary content before generation

## Non-Goals

The MVP filter is not a full PII detection system. It does not classify names,
addresses, account numbers, or free-form sensitive content. Those require a
broader product/security decision.

## Logging Rule

Do not log raw user query or review content. Request logs should use request id,
locale, status, and source counts instead.
