"""Evaluation seeds must not leak variants, invented IDs or unmarked provenance."""
import json
from pathlib import Path

import pytest

from app.evaluation.dataset import load_dataset
from scripts.rag_api_smoke_test import CASES

DATA = Path('evaluation/seeds/v1')


def test_seed_cases_and_sources_are_resolved_and_balanced():
    for name in ['culture', 'recommendation']:
        dataset = load_dataset(DATA / f'{name}.json')
        assert len(dataset.cases) == 20
        assert sum(case.split == 'dev' for case in dataset.cases) == 10
        assert sum(case.split == 'test' for case in dataset.cases) == 10
        assert dataset.provenance.kind == 'synthetic'
        assert dataset.provenance.humanReviewed is False
    culture = load_dataset(DATA / 'culture.json')
    assert {case.query for case in CASES} <= {case.query for case in culture.cases}
    catalog = json.loads((DATA / 'catalog.json').read_text())
    assert {entry['id'] for entry in catalog['items']} == set(range(101, 113))
    assert {entry['priceKrw'] for entry in catalog['items']} >= {'50000', '50000.01', '49999.99'}

@pytest.mark.parametrize('mutation', ['leak', 'source', 'hash', 'overlap', 'unknown'])
def test_loader_rejects_corrupt_or_leaky_dataset(tmp_path, mutation):
    raw = json.loads((DATA / 'culture.json').read_text())
    # Copy referenced corpus so the loader checks content rather than failing on missing files.
    (tmp_path / 'culture-corpus.json').write_bytes((DATA / 'culture-corpus.json').read_bytes())
    if mutation == 'leak':
        raw['cases'][1]['groupId'] = raw['cases'][0]['groupId']
        raw['cases'][1]['split'] = 'test' if raw['cases'][0]['split'] == 'dev' else 'dev'
    elif mutation == 'source':
        raw['cases'][0]['expectedSourceIds'] = ['unknown-document']
    elif mutation == 'hash':
        raw['snapshotHash'] = '0' * 64
    elif mutation == 'overlap':
        raw['cases'][0]['allowedIds'] = [101]
        raw['cases'][0]['forbiddenIds'] = [101]
    else:
        raw['unexpected'] = True
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_dataset(path)
