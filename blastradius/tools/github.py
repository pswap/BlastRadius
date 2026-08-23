from typing import Protocol
import re
import requests
from blastradius.models import PullRequest, ChangedFile


class GitHubClient(Protocol):
    def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest: ...
    def get_changed_files(self, owner: str, repo: str, number: int) -> list[ChangedFile]: ...
    def get_commits(self, owner: str, repo: str, number: int) -> list[str]: ...
    def get_pull_comments(self, owner: str, repo: str, number: int) -> list[dict]: ...
    def get_file_content(self, owner: str, repo: str, path: str, ref: str = "main") -> str: ...
    def search_repository_history(self, owner: str, repo: str, query: str) -> list[dict]: ...


class RealGitHubClient:
    def __init__(self, token: str):
        self.headers = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {token}"} if token else {})}
    def _get(self, path: str):
        response = requests.get(f"https://api.github.com{path}", headers=self.headers, timeout=20)
        response.raise_for_status(); return response.json()
    def get_changed_files(self, owner, repo, number):
        return [ChangedFile(path=f["filename"], status=f["status"], additions=f["additions"], deletions=f["deletions"], patch=f.get("patch", "")) for f in self._get(f"/repos/{owner}/{repo}/pulls/{number}/files")]
    def get_commits(self, owner, repo, number):
        return [c["sha"] for c in self._get(f"/repos/{owner}/{repo}/pulls/{number}/commits")]
    def get_pull_request(self, owner, repo, number):
        d = self._get(f"/repos/{owner}/{repo}/pulls/{number}")
        files = self.get_changed_files(owner, repo, number)
        return PullRequest(owner=owner, repo=repo, number=number, title=d["title"], body=d.get("body") or "", author=d["user"]["login"], url=d["html_url"], changed_files=files, commits=self.get_commits(owner, repo, number), labels=[x["name"] for x in d.get("labels", [])], diff="\n".join(f.patch for f in files))
    def get_pull_comments(self, owner, repo, number): return self._get(f"/repos/{owner}/{repo}/pulls/{number}/comments")
    def get_file_content(self, owner, repo, path, ref="main"):
        return self._get(f"/repos/{owner}/{repo}/contents/{path}?ref={ref}").get("content", "")
    def search_repository_history(self, owner, repo, query):
        return self._get(f"/search/issues?q={query}+repo:{owner}/{repo}+is:pr").get("items", [])


class MockGitHubClient:
    def __init__(self, pr: PullRequest): self.pr = pr
    def get_pull_request(self, owner, repo, number): return self.pr
    def get_changed_files(self, owner, repo, number): return self.pr.changed_files
    def get_commits(self, owner, repo, number): return self.pr.commits
    def get_pull_comments(self, owner, repo, number): return []
    def get_file_content(self, owner, repo, path, ref="main"): return ""
    def search_repository_history(self, owner, repo, query): return []


def parse_pr_url(url: str) -> tuple[str, str, int]:
    match = re.fullmatch(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?", url.strip())
    if not match: raise ValueError("Enter a GitHub PR URL such as https://github.com/org/repo/pull/123")
    return match.group(1), match.group(2), int(match.group(3))
