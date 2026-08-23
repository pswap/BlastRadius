from typing import TypedDict


class AgentState(TypedDict, total=False):
    owner: str
    repo: str
    number: int
    callback: object
    progress: list[str]
    pr: object
    components: list
    tests: list
    history: list
    records: list
    tests: list
    score: int
    level: object
    factors: list
    report: object
