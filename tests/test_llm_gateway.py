from unittest.mock import MagicMock

from codepipeline.llm_gateway import LLMGateway, retry


def test_retry_decorator_success():
    calls = {"n": 0}
    @retry(times=3, delay=0)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ValueError("fail")
        return "ok"
    assert flaky() == "ok"
    assert calls["n"] == 2

def test_gateway_injection():
    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="hi"))]
    fake_client.chat.completions.create.return_value = fake_resp
    gw = LLMGateway(client=fake_client)
    assert gw.chat([{"role":"user","content":"hi"}]) == "hi"
    fake_client.chat.completions.create.assert_called_once()
