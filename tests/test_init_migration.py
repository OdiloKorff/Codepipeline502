import os
import tempfile
from codepipeline.migrations.init_migration import init_migration

def test_init_migration(tmp_path, capsys):
    # Setup fake db files
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    # Create dummy db files and other files
    db1 = src / "project_history.db"
    txt = src / "readme.txt"
    db1.write_text("dummy")
    txt.write_text("text")
    # Run migration
    init_migration(str(src), str(dst))
    # Check migration
    assert not db1.exists()
    assert (dst / "project_history.db").exists()
    assert (src / "readme.txt").exists()