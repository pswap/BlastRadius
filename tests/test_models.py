from blastradius.models import PullRequest

def test_pr_is_json_serializable():
    pr = PullRequest(owner="o", repo="r", number=1, title="x", url="https://example.test")
    assert PullRequest.model_validate_json(pr.model_dump_json()).number == 1
