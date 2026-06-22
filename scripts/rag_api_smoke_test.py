import os
import sys
from dataclasses import dataclass
from typing import Any

import httpx


API_BASE_URL = os.getenv("RAG_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
TIMEOUT_SECONDS = float(os.getenv("RAG_API_TIMEOUT_SECONDS", "60"))


@dataclass(frozen=True)
class SmokeCase:
    query: str
    expected_terms: tuple[str, ...]
    locale: str = "ko"
    require_match: bool = True


CASES = (
    SmokeCase("조선시대 궁중 자수에 대해 알려주세요", ("자수장",)),
    SmokeCase("한산모시짜기에 대해 알려주세요", ("한산모시짜기",)),
    SmokeCase("판소리 배우고 싶어요", ("판소리",)),
    SmokeCase("매듭 공예가 뭐예요", ("매듭장",)),
    SmokeCase("도자기 만드는 전통 기술", ("도자", "도예", "도기", "사기")),
    SmokeCase("우주여행 로켓 발사", tuple(), require_match=False),
)


def explain(client: httpx.Client, case: SmokeCase) -> dict[str, Any]:
    response = client.post(
        "/api/v1/ai/explain",
        json={"query": case.query, "locale": case.locale},
    )
    response.raise_for_status()
    return response.json()


def result_terms(payload: dict[str, Any]) -> list[str]:
    sources = payload.get("sources") or []
    source_names = [source.get("name", "") for source in sources if isinstance(source, dict)]
    matching_keywords = payload.get("matchingKeywords") or []
    return [term for term in [*source_names, *matching_keywords] if isinstance(term, str)]


def matches_expected(terms: list[str], expected_terms: tuple[str, ...]) -> bool:
    return any(expected in term for expected in expected_terms for term in terms)


def run() -> int:
    if not INTERNAL_API_KEY:
        print("INTERNAL_API_KEY is required.", file=sys.stderr)
        return 2

    failures = 0
    headers = {"X-Internal-Api-Key": INTERNAL_API_KEY}
    with httpx.Client(base_url=API_BASE_URL, headers=headers, timeout=TIMEOUT_SECONDS) as client:
        for case in CASES:
            try:
                payload = explain(client, case)
            except httpx.HTTPError as error:
                failures += 1
                print(f"[FAIL] {case.query}")
                print(f"  request error: {error}\n")
                continue

            terms = result_terms(payload)
            matched = matches_expected(terms, case.expected_terms)
            passed = matched if case.require_match else not terms

            if passed:
                print(f"[PASS] {case.query}")
            else:
                failures += 1
                print(f"[FAIL] {case.query}")

            expected = ", ".join(case.expected_terms) if case.expected_terms else "(no strong match)"
            actual = ", ".join(terms) if terms else "(none)"
            print(f"  expected: {expected}")
            print(f"  sources/keywords: {actual}\n")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
