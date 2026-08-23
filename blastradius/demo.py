from pathlib import Path
from blastradius.models import PullRequest
from blastradius.tools import MockGitHubClient, MockGreptileClient
from blastradius.memory import MemoryStore, seed_demo
from blastradius.agent import BlastRadiusAgent

ROOT = Path(__file__).resolve().parents[1]


def demo_pr() -> PullRequest:
    return PullRequest.model_validate_json((ROOT / "data/demo/pr.json").read_text())


def demo_agent() -> BlastRadiusAgent:
    store = MemoryStore()
    seed_demo(store)
    return BlastRadiusAgent(MockGitHubClient(demo_pr()), MockGreptileClient(), store)
