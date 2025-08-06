from unittest.mock import patch

from codepipeline.rollback import check_canary, git_revert


@patch("codepipeline.rollback._fetch_metrics", return_value={"error_rate":0.01})
def test_check_canary_pass(mock_f):
    assert check_canary("http://dummy")

@patch("codepipeline.rollback._fetch_metrics", return_value={"error_rate":0.2})
def test_check_canary_fail(mock_f):
    assert not check_canary("x")

@patch("codepipeline.rollback.git.Repo")
def test_git_revert(mock_repo):
    git_revert("/tmp")
    mock_repo.assert_called_with("/tmp")
    mock_repo.return_value.git.reset.assert_called()
