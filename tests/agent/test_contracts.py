"""Contract tests catch relaxed boundaries, precision loss and inconsistent outcomes."""
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.agent import (AgentConstraints, AgentRequest, AgentResponse,
                               CatalogExperienceResponse, CatalogSearchRequest)

CONTRACTS = Path('docs/contracts/agent-v1')

@pytest.mark.parametrize('amount', ['50000', '50000.01', '49999.99', 50000.01, '0'])
def test_price_preserves_decimal_boundary(amount):
    constraints = AgentConstraints(maxPriceKrw=amount, headCount=3)
    assert constraints.maxPriceKrw == Decimal(str(amount))
    assert json.loads(constraints.model_dump_json())['maxPriceKrw'] == str(amount)

@pytest.mark.parametrize('fields', [
    {'headCount': 0}, {'headCount': 21}, {'headCount': 1.5},
    {'maxPriceKrw': '-0.01'}, {'maxPriceKrw': '50000.001'},
    {'maxPriceKrw': 'NaN'}, {'regionCode': 'DAEGU'}, {'unknown': True},
])
def test_constraints_reject_invalid_boundaries(fields):
    with pytest.raises(ValidationError):
        AgentConstraints(**fields)

@pytest.mark.parametrize('payload', [
    {'query': ''}, {'query': '   '}, {'query': '가' * 501},
    {'query': '한지', 'locale': 'en'}, {'query': '한지', 'extra': 1},
    {'query': '한지', 'constraints': {'unknown': 1}},
])
def test_request_rejects_invalid_scope(payload):
    with pytest.raises(ValidationError):
        AgentRequest(**payload)


def test_catalog_defaults_and_trim():
    request = CatalogSearchRequest(queryTerms=['  한지  '])
    assert request.queryTerms == ['한지']
    assert request.limit == 5
    assert request.constraints.headCount == 1

@pytest.mark.parametrize('payload', [
    {'queryTerms': []}, {'queryTerms': ['a'] * 6}, {'queryTerms': [' ']},
    {'queryTerms': ['a' * 51]}, {'queryTerms': ['한지'], 'limit': 0},
    {'queryTerms': ['한지'], 'limit': 11}, {'queryTerms': ['한지'], 'regionCode': 'SEOUL'},
])
def test_catalog_rejects_invalid_search(payload):
    with pytest.raises(ValidationError):
        CatalogSearchRequest(**payload)


def test_shared_examples_round_trip_without_price_loss():
    for file, model in [('request.json', AgentRequest), ('completed.json', AgentResponse),
                        ('clarification.json', AgentResponse), ('catalog-item.json', CatalogExperienceResponse),
                        ('catalog-search.json', CatalogSearchRequest)]:
        raw = json.loads((CONTRACTS / file).read_text())
        assert json.loads(model.model_validate(raw).model_dump_json()) == raw

@pytest.mark.parametrize('mutation', [
    {'status': 'success'}, {'recommendedExperienceIds': [102]},
    {'status': 'clarification_required'}, {'status': 'no_match'},
    {'unsupportedConstraints': ['weekend']}, {'extra': 1},
])
def test_response_rejects_inconsistent_result(mutation):
    raw = json.loads((CONTRACTS / 'completed.json').read_text())
    raw.update(mutation)
    with pytest.raises(ValidationError):
        AgentResponse.model_validate(raw)


def test_shared_invalid_examples_are_rejected():
    models = {model.__name__: model for model in (AgentConstraints, AgentRequest, CatalogSearchRequest)}
    for example in json.loads((CONTRACTS / 'invalid-examples.json').read_text()):
        with pytest.raises(ValidationError):
            models[example['model']].model_validate(example['payload'])
