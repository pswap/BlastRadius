from pydantic import BaseModel, Field


class ChangedFile(BaseModel):
    path: str
    status: str = "modified"
    additions: int = 0
    deletions: int = 0
    patch: str = ""


class PullRequest(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    body: str = ""
    author: str = "unknown"
    url: str
    changed_files: list[ChangedFile] = Field(default_factory=list)
    commits: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    diff: str = ""
