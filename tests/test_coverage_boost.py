import importlib
import pkgutil

import codepipeline


def test_import_all_public_modules():
    pkg=codepipeline
    for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        name = m.name
        if ".tests" in name:
            continue
        importlib.import_module(name)

def test_retry_decorator():
    from codepipeline.llm_gateway import retry
    calls={"n":0}
    @retry(times=2, delay=0)
    def flaky():
        calls["n"]+=1
        if calls["n"]<2:
            raise ValueError("fail")
        return "ok"
    assert flaky()=="ok"
