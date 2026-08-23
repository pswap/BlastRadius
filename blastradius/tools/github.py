"""Isolated adapter for GitHub's official REST API."""
from __future__ import annotations

import base64
import re
from typing import Any, Protocol
from urllib.parse import quote

import requests

from blastradius.models import ChangedFile, PullRequest


class GitHubAPIError(RuntimeError):
    """Safe, user-facing API error that never includes credentials."""


class GitHubClient(Protocol):
    def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest: ...
    def get_changed_files(self, owner: str, repo: str, number: int) -> list[ChangedFile]: ...
    def get_commits(self, owner: str, repo: str, number: int) -> list[str]: ...
    def get_pull_comments(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]: ...
    def get_file_content(self, owner: str, repo: str, path: str, ref: str = "main") -> str: ...


class RealGitHubClient:
    """Maps internal Pydantic models to GitHub REST API responses."""
    base_url = "https://api.github.com"

    def __init__(self, token: str = "", session: requests.Session | Any | None = None):
        self.session = session or requests.Session()
        self.headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str) -> Any:
        try:
            response = self.session.get(f"{self.base_url}{path}", headers=self.headers, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise GitHubAPIError("GitHub request timed out. Please try again.") from exc
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", None)
            message = "GitHub API request failed. Please try again."
            if status == 401: message = "GitHub authentication failed. Check GITHUB_TOKEN."
            elif status == 403: message = "GitHub denied this request. Check token permissions or rate limits."
            elif status == 404: message = "Pull request or repository was not found."
            raise GitHubAPIError(message) from exc
        except ValueError as exc:
            raise GitHubAPIError("GitHub returned an unexpected response.") from exc

    def get_changed_files(self, owner: str, repo: str, number: int) -> list[ChangedFile]:
        data = self._get(f"/repos/{owner}/{repo}/pulls/{number}/files")
        return [ChangedFile(path=f["filename"], status=f["status"], additions=f["additions"], deletions=f["deletions"], patch=f.get("patch", "")) for f in data]

    def get_commits(self, owner: str, repo: str, number: int) -> list[str]:
        return [commit["sha"] for commit in self._get(f"/repos/{owner}/{repo}/pulls/{number}/commits")]

    def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest:
        data = self._get(f"/repos/{owner}/{repo}/pulls/{number}")
        files = self.get_changed_files(owner, repo, number)
        return PullRequest(owner=owner, repo=repo, number=number, title=data["title"], body=data.get("body") or "", author=data["user"]["login"], url=data["html_url"], changed_files=files, commits=self.get_commits(owner, repo, number), labels=[label["name"] for label in data.get("labels", [])], diff="\n".join(file.patch for file in files))

    def get_pull_comments(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        return self._get(f"/repos/{owner}/{repo}/pulls/{number}/comments")

    def get_file_content(self, owner: str, repo: str, path: str, ref: str = "main") -> str:
        data = self._get(f"/repos/{owner}/{repo}/contents/{quote(path)}?ref={quote(ref)}")
        if data.get("encoding") == "base64":
            return base64.b64decode(data.get("content", "").replace("\n", "")).decode("utf-8")
        return data.get("content", "")


class MockGitHubClient:
    def __init__(self, pr: PullRequest, comments: list[dict[str, Any]] | None = None, files: dict[str, str] | None = None):
        self.pr, self.comments, self.files = pr, comments or [], files or {}

    def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest: return self.pr
    def get_changed_files(self, owner: str, repo: str, number: int) -> list[ChangedFile]: return self.pr.changed_files
    def get_commits(self, owner: str, repo: str, number: int) -> list[str]: return self.pr.commits
    def get_pull_comments(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]: return self.comments
    def get_file_content(self, owner: str, repo: str, path: str, ref: str = "main") -> str: return self.files.get(path, "")


def parse_pr_url(url: str) -> tuple[str, str, int]:
    match = re.fullmatch(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?", url.strip())
    if not match:
        raise ValueError("Enter a GitHub PR URL such as https://github.com/org/repo/pull/123")
    return match.group(1), match.group(2), int(match.group(3))
