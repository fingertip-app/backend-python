"""Contract tests catch relaxed boundaries, precision loss and inconsistent outcomes."""
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.agent import (AgentConstraints, AgentRequest, AgentResponse,
                               CatalogExperienceResponse, CatalogSearchRequest, CatalogExperienceDetailsResponse,
                               CultureSearchRequest, CultureSearchResponse, AgentDraft)

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
                        ('catalog-search.json', CatalogSearchRequest), ('catalog-detail.json', CatalogExperienceDetailsResponse),
                        ('culture-search.json', CultureSearchRequest), ('culture-documents.json', CultureSearchResponse),
                        ('draft.json', AgentDraft)]:
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


def test_raw_json_preserves_large_numeric_decimal_without_rounding():
    constraints = AgentConstraints.model_validate_json('{"maxPriceKrw":9007199254740993.01}')
    assert constraints.maxPriceKrw == Decimal('9007199254740993.01')
    assert json.loads(constraints.model_dump_json())['maxPriceKrw'] == '9007199254740993.01'


def test_raw_json_rejects_original_excess_precision_before_rounding():
    with pytest.raises(ValidationError):
        AgentConstraints.model_validate_json('{"maxPriceKrw":50000.000000000001}')


@pytest.mark.parametrize('amount,accepted', [
    ('50000.01', True), ('9007199254740993.01', True), ('0', True), ('1.000', True),
    ('-0.01', False), ('50000.001', False), ('50000.000000000001', False),
    ('1e2', False), ('+1', False), ('NaN', False),
])
def test_price_string_schema_and_runtime_accept_the_same_forms(amount, accepted):
    import jsonschema

    schema = json.loads((CONTRACTS / 'AgentRequest.validation.schema.json').read_text())
    payload = {'query': '한지', 'constraints': {'maxPriceKrw': amount}}
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(payload))
    assert (not errors) is accepted
    if accepted:
        AgentRequest.model_validate(payload)
    else:
        with pytest.raises(ValidationError):
            AgentRequest.model_validate(payload)


@pytest.mark.parametrize('amount,accepted', [(Decimal('50000.01'), True), (Decimal('50000.001'), False), (Decimal('-0.01'), False)])
def test_price_numeric_validation_schema_enforces_nonnegative_cents(amount, accepted):
    import jsonschema

    schema = json.loads((CONTRACTS / 'AgentRequest.validation.schema.json').read_text(), parse_float=Decimal)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors({'query': '한지', 'constraints': {'maxPriceKrw': amount}}))
    assert (not errors) is accepted


def test_shared_raw_decimal_examples_keep_original_numeric_tokens():
    for example in json.loads((CONTRACTS / 'decimal-wire-examples.json').read_text()):
        if example['valid']:
            value = AgentConstraints.model_validate_json(example['inputJson'])
            assert json.loads(value.model_dump_json())['maxPriceKrw'] == example['maxPriceKrw']
        else:
            with pytest.raises(ValidationError):
                AgentConstraints.model_validate_json(example['inputJson'])
