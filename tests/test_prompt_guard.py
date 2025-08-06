from codepipeline.prompt_guard import (
    PromptTemplate,
    SoftAbort,
    apply_fewshot_template,
    evaluate_prompt_quality,
    sanitize_input,
)


def test_quality_scoring():
    assert evaluate_prompt_quality("Short") < 0.2
    good = "Please generate code. Example: input X, expected output Y."
    assert evaluate_prompt_quality(good) > 0.4

def test_sanitizing():
    dirty = "<script>alert(1)</script> SELECT * FROM users"
    cleaned = sanitize_input(dirty)
    assert "<script" not in cleaned.lower()
    assert "alert" not in cleaned.lower()

def test_template_soft_abort():
    tmpl = PromptTemplate(name="t", system="sys", min_score=0.5)
    try:
        apply_fewshot_template("bad", tmpl)
    except SoftAbort:
        assert True
    else:
        raise AssertionError()
