from unittest.mock import patch, MagicMock
from codepipeline.post_merge_runner import run_tests

@patch("codepipeline.post_merge_runner.subprocess.run")
def test_run_tests_success(mock_run):
    mock_proc=MagicMock(returncode=0,stdout="ok",stderr="")
    mock_run.return_value=mock_proc
    res=run_tests("/tmp",timeout=1,webhook_url=None)
    assert res["success"] is True
    mock_run.assert_called()

@patch("codepipeline.post_merge_runner.requests.post")
@patch("codepipeline.post_merge_runner.subprocess.run")
def test_webhook_called(mock_run,mock_post):
    mock_proc=MagicMock(returncode=1,stdout="",stderr="f")
    mock_run.return_value=mock_proc
    res=run_tests("/tmp",webhook_url="http://example.com")
    mock_post.assert_called_once()
    assert res["success"] is False