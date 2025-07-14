
from unittest.mock import patch, MagicMock
from codepipeline import canary_watcher as cw

@patch("codepipeline.canary_watcher.requests.patch")
def test_traffic_shift(mock_patch):
    mock_patch.return_value.status_code=200
    cw.traffic_shift(5)
    mock_patch.assert_called()

@patch("codepipeline.canary_watcher._error_rate", return_value=1.0)
@patch("codepipeline.canary_watcher._git_revert")
@patch("codepipeline.canary_watcher._helm_rollback")
@patch("codepipeline.canary_watcher.traffic_shift")
def test_watch_triggers(mock_ts, mock_hr, mock_gr, mock_er):
    cw.watch_and_rollback(interval=0.01, WINDOW=0.02)  # adjust via monkeypatch not available, so call directly
