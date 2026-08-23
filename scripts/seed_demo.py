from blastradius.memory import MemoryStore, seed_demo

store = MemoryStore("blastradius.db")
seed_demo(store)
print("Seeded demo engineering memory in blastradius.db")
