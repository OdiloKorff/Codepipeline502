
from codepipeline.patch_engine import CONFLICT_MID, insert_snippet, merge_three_way


def test_insert_snippet_after():
    src = "def foo():\n    pass\n"
    snippet = "print('hi')\n"
    out = insert_snippet(src, snippet, anchor="foo")
    assert "print('hi')" in out.splitlines()[2]


def test_merge_three_way_conflict_marker():
    base, loc, rem = "a", "b", "c"
    merged = merge_three_way(base, loc, rem)
    assert CONFLICT_MID in merged
