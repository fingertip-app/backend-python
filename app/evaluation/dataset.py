"""Load versioned offline seeds and verify their exact referenced fixture snapshot."""
import hashlib
import json
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from app.schemas.agent import (AgentConstraints, AgentStatus, CatalogExperienceResponse,
                               CultureDocument, StrictContract, Text)


class Provenance(StrictContract):
    kind: Literal['synthetic', 'heritage_snapshot']
    createdOn: str
    source: Text
    humanReviewed: bool
    note: Text


class EvaluationCase(StrictContract):
    id: Text
    groupId: Text
    split: Literal['dev', 'test']
    category: Text
    query: str = Field(min_length=1, max_length=500)
    locale: Literal['ko'] = 'ko'
    constraints: AgentConstraints = Field(default_factory=AgentConstraints)
    supportedMode: Literal['culture', 'recommendation']
    allowedIds: list[int]
    forbiddenIds: list[int]
    expectedStatus: AgentStatus
    expectedSourceIds: list[str]
    unsupportedConstraints: list[str] = Field(default_factory=list)
    conflict: bool = False
    rationale: Text

    @model_validator(mode='after')
    def check_expectations(self) -> Self:
        if set(self.allowedIds) & set(self.forbiddenIds):
            raise ValueError('Allowed and forbidden IDs overlap')
        if self.expectedStatus != AgentStatus.COMPLETED and self.allowedIds:
            raise ValueError('Non-completed seed cannot allow recommendations')
        if (self.conflict or self.unsupportedConstraints) and self.expectedStatus != AgentStatus.CLARIFICATION_REQUIRED:
            raise ValueError('Conflict and unsupported conditions require clarification')
        return self


class EvaluationDataset(StrictContract):
    schemaVersion: Literal['1']
    dataset: Literal['culture', 'recommendation']
    provenance: Provenance
    corpusFile: Text
    snapshotHash: str = Field(pattern=r'^[a-f0-9]{64}$')
    cases: list[EvaluationCase] = Field(min_length=1)

    @model_validator(mode='after')
    def check_groups(self) -> Self:
        seen_ids: set[str] = set()
        group_splits: dict[str, str] = {}
        for case in self.cases:
            if case.id in seen_ids:
                raise ValueError('Duplicate case ID')
            seen_ids.add(case.id)
            if case.supportedMode != self.dataset:
                raise ValueError('Case mode does not match dataset')
            if case.groupId in group_splits and group_splits[case.groupId] != case.split:
                raise ValueError('Paraphrase group leaks across dev/test')
            group_splits[case.groupId] = case.split
        return self


class CatalogFixtureItem(CatalogExperienceResponse):
    address: str


class CatalogFixture(StrictContract):
    provenance: Provenance
    items: list[CatalogFixtureItem]


class CultureFixture(StrictContract):
    provenance: Provenance
    documents: list[CultureDocument]


def load_dataset(path: Path | str) -> EvaluationDataset:
    path = Path(path)
    dataset = EvaluationDataset.model_validate_json(path.read_bytes())
    corpus_path = (path.parent / dataset.corpusFile).resolve()
    if corpus_path.parent != path.parent.resolve():
        raise ValueError('Corpus must be a sibling fixture file')
    corpus_bytes = corpus_path.read_bytes()
    if hashlib.sha256(corpus_bytes).hexdigest() != dataset.snapshotHash:
        raise ValueError('Fixture snapshot hash mismatch')
    raw = json.loads(corpus_bytes)
    if dataset.dataset == 'culture':
        corpus = CultureFixture.model_validate(raw)
        ids = [document.documentId for document in corpus.documents]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate culture document ID')
        for case in dataset.cases:
            if case.allowedIds or case.forbiddenIds:
                raise ValueError('Culture case cannot reference experience IDs')
            if not set(case.expectedSourceIds) <= set(ids):
                raise ValueError('Expected document ID is absent from fixture snapshot')
    else:
        catalog = CatalogFixture.model_validate(raw)
        ids = [item.id for item in catalog.items]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate catalog ID')
        for case in dataset.cases:
            if not set(case.allowedIds + case.forbiddenIds) <= set(ids):
                raise ValueError('Expected experience ID is absent from fixture snapshot')
            if case.expectedSourceIds:
                raise ValueError('Recommendation case cannot assert culture sources')
    if dataset.provenance.kind != raw['provenance']['kind']:
        raise ValueError('Dataset provenance does not match corpus')
    return dataset
