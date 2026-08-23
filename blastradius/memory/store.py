import json
import sqlite3
from blastradius.models import MemoryRecord


class MemoryStore:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, type TEXT, title TEXT, description TEXT, date TEXT, source TEXT, tags TEXT, affected_components TEXT, outcome TEXT)""")
    def add_memory(self, record: MemoryRecord) -> None:
        self.conn.execute("INSERT OR REPLACE INTO memories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (record.id, record.type, record.title, record.description, record.date, record.source, json.dumps(record.tags), json.dumps(record.affected_components), record.outcome)); self.conn.commit()
    def get_memory(self, record_id: str) -> MemoryRecord | None:
        row = self.conn.execute("SELECT * FROM memories WHERE id=?", (record_id,)).fetchone(); return self._record(row) if row else None
    def list_memories(self) -> list[MemoryRecord]: return [self._record(r) for r in self.conn.execute("SELECT * FROM memories ORDER BY date DESC")]
    def search_memory(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        words = {w.lower().strip(".,#") for w in query.split() if len(w) > 2}
        def score(r):
            text = " ".join([r.title, r.description, r.outcome, *r.tags, *r.affected_components]).lower()
            return sum(w in text for w in words)
        return sorted((r for r in self.list_memories() if score(r)), key=score, reverse=True)[:limit]
    @staticmethod
    def _record(row): return MemoryRecord(id=row[0], type=row[1], title=row[2], description=row[3], date=row[4], source=row[5], tags=json.loads(row[6]), affected_components=json.loads(row[7]), outcome=row[8])
