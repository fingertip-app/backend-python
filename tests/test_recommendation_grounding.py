from types import SimpleNamespace

import pytest

from app.services.ai.experience_rag import ExperienceRagService
from app.services.ai.rag import CultureRagService


@pytest.mark.parametrize("term", ["청자", "도자기", "도예", "사기장", "달항아리"])
def test_general_pottery_terms_do_not_assert_white_porcelain(term):
    tags = CultureRagService._map_to_app_tags([term])
    assert "백자" not in tags
    assert "도자기" in tags


def test_explicit_white_porcelain_preserves_specific_tag():
    assert "백자" in CultureRagService._map_to_app_tags(["백자"])


@pytest.mark.parametrize("query", [
    "가족과 함께", "혼자 가고 싶어요", "조용한 체험", "만들기", "family", "solo",
])
def test_query_alone_does_not_prove_experience_suitability(query):
    experience = SimpleNamespace(category="도자기")
    reason = ExperienceRagService(None)._extract_match_reason(experience, query)
    assert reason == "도자기 분야로 등록된 체험입니다. 참여 조건은 상세 정보를 확인해 주세요."
