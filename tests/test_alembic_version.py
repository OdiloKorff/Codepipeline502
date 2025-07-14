
import subprocess

def test_alembic_current_head():
    output = subprocess.check_output(["alembic", "current"], text=True)
    assert "head" in output.lower()
