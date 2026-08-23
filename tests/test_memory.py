from blastradius.memory import MemoryStore, seed_demo

def test_keyword_memory_search():
    store = MemoryStore(); seed_demo(store)
    found = store.search_memory("payment retry kafka")
    assert found[0].id == "PR-101"
