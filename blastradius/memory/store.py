"""Small SQLite engineering-memory store with keyword and optional semantic search."""
from __future__ import annotations

import json
import math
import re
import sqlite3
from typing import Iterable

from blastradius.models import MemoryRecord
from .embeddings import EmbeddingProvider


class MemoryStore:
    def __init__(self, path: str = ":memory:", embedding_provider: EmbeddingProvider | None = None):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.embedding_provider = embedding_provider
        self.initialize()

    def initialize(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY, type TEXT NOT NULL, title TEXT NOT NULL,
                description TEXT NOT NULL, date TEXT NOT NULL, source TEXT NOT NULL,
                tags TEXT NOT NULL, affected_components TEXT NOT NULL,
                outcome TEXT NOT NULL, embedding TEXT
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_date ON memories(date DESC)")
        self.conn.commit()

    @staticmethod
    def _document(record: MemoryRecord) -> str:
        return " ".join([record.title, record.description, record.outcome, *record.tags, *record.affected_components])

    def _embed(self, text: str) -> list[float] | None:
        if not self.embedding_provider:
            return None
        try:
            vector = self.embedding_provider.embed(text)
            if not vector or not all(isinstance(value, (int, float)) for value in vector):
                return None
            return [float(value) for value in vector]
        except Exception:
            # Embedding availability must never prevent deterministic fallback search.
            return None

    def add_memory(self, record: MemoryRecord) -> None:
        embedding = self._embed(self._document(record))
        self.conn.execute("""INSERT OR REPLACE INTO memories
            (id, type, title, description, date, source, tags, affected_components, outcome, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                record.id, record.type, record.title, record.description, record.date,
                record.source, json.dumps(record.tags), json.dumps(record.affected_components),
                record.outcome, json.dumps(embedding) if embedding is not None else None,
            ))
        self.conn.commit()

    def get_memory(self, record_id: str) -> MemoryRecord | None:
        row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (record_id,)).fetchone()
        return self._record(row) if row else None

    def list_memories(self, memory_type: str | None = None) -> list[MemoryRecord]:
        query, params = "SELECT * FROM memories", []
        if memory_type:
            query += " WHERE type = ?"; params.append(memory_type)
        query += " ORDER BY date DESC, id DESC"
        return [self._record(row) for row in self.conn.execute(query, params)]

    @staticmethod
    def _keywords(text: str) -> set[str]:
        return {word.lower() for word in re.findall(r"[A-Za-z0-9_]+", text) if len(word) > 2}

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right): return 0.0
        denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(y * y for y in right))
        return sum(x * y for x, y in zip(left, right)) / denominator if denominator else 0.0

    def search_memory(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Uses embeddings when available; otherwise ranks deterministic keyword overlap."""
        records = self.list_memories()
        query_embedding = self._embed(query)
        query_words = self._keywords(query)
        scored: list[tuple[float, MemoryRecord]] = []
        for record in records:
            keyword_score = len(query_words & self._keywords(self._document(record)))
            row = self.conn.execute("SELECT embedding FROM memories WHERE id = ?", (record.id,)).fetchone()
            stored_embedding = json.loads(row["embedding"]) if row["embedding"] else None
            semantic_score = self._cosine(query_embedding, stored_embedding) if query_embedding and stored_embedding else 0.0
            score = semantic_score * 100 + keyword_score
            if score > 0: scored.append((score, record))
        return [record for _, record in sorted(scored, key=lambda pair: (pair[0], pair[1].date), reverse=True)[:limit]]

    @staticmethod
    def _record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(id=row["id"], type=row["type"], title=row["title"], description=row["description"], date=row["date"], source=row["source"], tags=json.loads(row["tags"]), affected_components=json.loads(row["affected_components"]), outcome=row["outcome"])
