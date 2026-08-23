from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    greptile_api_key: str = os.getenv("GREPTILE_API_KEY", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_provider: str = os.getenv("LLM_PROVIDER", "")


settings = Settings()
