import pytest
from pydantic import ValidationError

from blastradius.memory import MemoryStore, seed_demo
from blastradius.models import MemoryRecord


def seeded_store(**kwargs):
    store = MemoryStore(**kwargs); seed_demo(store); return store


@pytest.mark.parametrize(("query", "expected_id"), [
    ("payment retry duplicate", "PR-101"),
    ("Kafka event schema", "PR-120"),
    ("FraudService compatibility", "PR-121"),
])
def test_seeded_keyword_searches_return_expected_history(query, expected_id):
    assert seeded_store().search_memory(query)[0].id == expected_id


def test_add_get_and_list_memory_records():
    store = MemoryStore()
    record = MemoryRecord(id="INC-1", type="incident", title="Cache outage", description="Cache connection failure", date="2025-01-01", source="incident channel", outcome="Recovered")
    store.add_memory(record)
    assert store.get_memory("INC-1") == record
    assert store.list_memories("incident") == [record]
    assert store.get_memory("missing") is None


@pytest.mark.parametrize("memory_type", ["incident", "pull_request", "postmortem", "architecture_decision", "engineering_note"])
def test_all_supported_memory_types_are_valid(memory_type):
    assert MemoryRecord(id=memory_type, type=memory_type, title="title", description="description", source="source").type == memory_type


def test_unknown_memory_type_is_rejected():
    with pytest.raises(ValidationError):
        MemoryRecord(id="x", type="unknown", title="title", description="description", source="source")


class FakeEmbeddings:
    def embed(self, text):
        return [1.0, 0.0] if text == "semantic target" or "unrelated wording" in text else [0.0, 1.0]


def test_semantic_search_is_used_when_embedding_provider_is_available():
    store = MemoryStore(embedding_provider=FakeEmbeddings())
    store.add_memory(MemoryRecord(id="SEM-1", type="engineering_note", title="semantic target", description="unrelated wording", source="note"))
    store.add_memory(MemoryRecord(id="SEM-2", type="engineering_note", title="other", description="semantic target keyword", source="note"))
    assert store.search_memory("semantic target")[0].id == "SEM-1"


class BrokenEmbeddings:
    def embed(self, text): raise RuntimeError("provider unavailable")


def test_keyword_fallback_survives_embedding_provider_failure():
    store = seeded_store(embedding_provider=BrokenEmbeddings())
    assert store.search_memory("payment retry duplicate")[0].id == "PR-101"
