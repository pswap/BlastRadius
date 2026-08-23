import base64
import pytest
import requests
from blastradius.models import ChangedFile, PullRequest
from blastradius.tools.github import GitHubAPIError, MockGitHubClient, RealGitHubClient, parse_pr_url


class Response:
    def __init__(self, payload, status=200): self.payload, self.status, self.status_code = payload, status, status
    def raise_for_status(self):
        if self.status >= 400:
            error = requests.HTTPError("request failed"); error.response = self; raise error
    def json(self): return self.payload


class Session:
    def __init__(self, responses): self.responses, self.paths, self.headers = list(responses), [], []
    def get(self, url, headers, timeout): self.paths.append(url); self.headers.append(headers); return self.responses.pop(0)


def test_parse_pr_url(): assert parse_pr_url("https://github.com/acme/payments/pull/123") == ("acme", "payments", 123)
def test_parse_pr_url_rejects_invalid():
    with pytest.raises(ValueError): parse_pr_url("not a url")

def test_real_client_normalizes_official_api_payloads():
    session = Session([Response({"title": "Improve retries", "body": None, "user": {"login": "siva"}, "html_url": "https://github.com/a/r/pull/1", "labels": [{"name": "reliability"}]}), Response([{"filename": "app.py", "status": "modified", "additions": 3, "deletions": 1, "patch": "+x"}]), Response([{"sha": "abc123"}])])
    pr = RealGitHubClient("secret-token", session).get_pull_request("a", "r", 1)
    assert pr.title == "Improve retries" and pr.changed_files[0].path == "app.py" and pr.commits == ["abc123"]
    assert "secret-token" not in str(session.paths) and session.headers[0]["X-GitHub-Api-Version"] == "2022-11-28"

def test_file_content_is_base64_decoded_and_paths_are_escaped():
    session = Session([Response({"encoding": "base64", "content": base64.b64encode(b"hello").decode()})])
    assert RealGitHubClient(session=session).get_file_content("a", "r", "docs/a file.md", "feature/test") == "hello"
    assert "docs/a%20file.md" in session.paths[0]

def test_http_errors_are_safe_and_never_include_token():
    session = Session([Response({}, 401)])
    with pytest.raises(GitHubAPIError, match="authentication failed") as error: RealGitHubClient("top-secret", session)._get("/bad")
    assert "top-secret" not in str(error.value)

def test_mock_client_returns_pydantic_pr_and_configured_data():
    pr = PullRequest(owner="a", repo="r", number=1, title="Test", author="me", url="https://github.com/a/r/pull/1", changed_files=[ChangedFile(path="a.py")])
    mock = MockGitHubClient(pr, comments=[{"body": "looks good"}], files={"a.py": "print(1)"})
    assert mock.get_pull_request("a", "r", 1).model_dump() == pr.model_dump()
    assert mock.get_pull_comments("a", "r", 1)[0]["body"] == "looks good" and mock.get_file_content("a", "r", "a.py") == "print(1)"
