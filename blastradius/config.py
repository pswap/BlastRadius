from dataclasses import dataclass
import os


def _default_greptile_repository() -> str:
    owner = os.getenv("GITHUB_OWNER", "").strip()
    repo = os.getenv("GITHUB_REPO", "").strip()
    return f"{owner}/{repo}" if owner and repo else ""


@dataclass(frozen=True)
class Settings:
    demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_owner: str = os.getenv("GITHUB_OWNER", "")
    github_repo: str = os.getenv("GITHUB_REPO", "")
    greptile_api_key: str = os.getenv("GREPTILE_API_KEY", "")
    greptile_repository: str = os.getenv("GREPTILE_REPOSITORY", _default_greptile_repository())
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_provider: str = os.getenv("LLM_PROVIDER", "")


settings = Settings()
