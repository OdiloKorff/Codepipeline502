import pathlib
import shutil
import tempfile

import toml
from scripts.bump_version import bump


def test_bump_version():
    tmpdir = tempfile.mkdtemp()
    py = pathlib.Path(tmpdir)/"pyproject.toml"
    py.write_text('[tool.poetry]\nname="x"\nversion="0.1.0"\n')
    new = bump(str(py))
    assert new == "0.1.1"
    data = toml.load(py)
    assert data["tool"]["poetry"]["version"] == "0.1.1"
    shutil.rmtree(tmpdir)
