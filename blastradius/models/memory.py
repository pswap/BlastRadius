from datetime import date
from typing import Literal
from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    id: str
    type: Literal["incident", "pull_request", "postmortem", "architecture_decision", "engineering_note"]
    title: str
    description: str
    date: str = Field(default_factory=lambda: str(date.today()))
    source: str
    tags: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    outcome: str = ""
