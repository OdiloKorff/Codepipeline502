
from orchestrator.flows import migrate


def test_migrate_signature():
    assert callable(migrate)
