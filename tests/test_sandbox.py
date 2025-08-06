from codepipeline.sandbox_runner import _validate_patch_file, run_patch


def test_validate_patch_file(tmp_path):
    f=tmp_path/'a.txt'
    f.write_text("x")
    _validate_patch_file(str(f))

def test_run_patch_denied():
    import pytest
    with pytest.raises(PermissionError):
        run_patch(["rm", "-rf", "/"])
