from unittest.mock import patch, MagicMock
from scripts import security_scan as ss

@patch("scripts.security_scan.subprocess.run")
def test_bandit_high_causes_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout='{"results":[{"issue_severity":"HIGH"}]}')
    assert ss.run_bandit() == 1