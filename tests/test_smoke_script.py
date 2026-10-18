from types import SimpleNamespace

from scripts import smoke_test


class FakeEmbeddings:
    def create(self, **kwargs):
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2])])


class FakeOpenAI:
    def __init__(self, api_key=None) -> None:
        self.embeddings = FakeEmbeddings()


class FakeDb:
    def execute(self, sql, params):
        return SimpleNamespace(
            fetchall=lambda: [
                SimpleNamespace(
                    title="판소리",
                    category="음악",
                    snippet="소리꾼과 고수가 함께하는 공연",
                    similarity=0.82,
                )
            ]
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_smoke_search_returns_structured_results(monkeypatch):
    monkeypatch.setattr(smoke_test, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(smoke_test, "SessionLocal", lambda: FakeDb())

    results = smoke_test.search("판소리")

    assert results == [
        {
            "title": "판소리",
            "category": "음악",
            "snippet": "소리꾼과 고수가 함께하는 공연",
            "similarity": 0.82,
        }
    ]
