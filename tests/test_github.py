import pytest
from blastradius.tools.github import parse_pr_url

def test_parse_pr_url(): assert parse_pr_url("https://github.com/acme/payments/pull/123") == ("acme", "payments", 123)
def test_parse_pr_url_rejects_invalid():
    with pytest.raises(ValueError): parse_pr_url("not a url")
