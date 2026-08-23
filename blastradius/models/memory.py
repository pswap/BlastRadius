from datetime import date
from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    id: str
    type: str
    title: str
    description: str
    date: str = Field(default_factory=lambda: str(date.today()))
    source: str
    tags: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    outcome: str = ""
