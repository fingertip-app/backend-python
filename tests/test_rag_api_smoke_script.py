from scripts import rag_api_smoke_test


def test_result_terms_combines_sources_and_matching_keywords():
    payload = {
        "sources": [
            {"name": "자수장", "category": "공예"},
            {"name": "궁중채화", "category": "공예"},
        ],
        "matchingKeywords": ["조선시대 자수"],
    }

    assert rag_api_smoke_test.result_terms(payload) == [
        "자수장",
        "궁중채화",
        "조선시대 자수",
    ]


def test_matches_expected_accepts_partial_source_match():
    terms = ["국가무형유산 자수장", "공예"]

    assert rag_api_smoke_test.matches_expected(terms, ("자수장",))


def test_matches_expected_rejects_unrelated_terms():
    terms = ["판소리", "음악"]

    assert not rag_api_smoke_test.matches_expected(terms, ("자수장",))
