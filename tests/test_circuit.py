from codepipeline.circuit import CircuitBreaker
import pytest

def test_circuit_opens_and_resets(monkeypatch):
    cb=CircuitBreaker(fail_max=2, reset_timeout=0.1)
    call_counter={"n":0}
    def fail():
        call_counter["n"]+=1
        raise ValueError("boom")
    # two failures -> open
    with pytest.raises(ValueError): cb.call(fail)
    with pytest.raises(ValueError): cb.call(fail)
    with pytest.raises(RuntimeError): cb.call(lambda: None)
    # wait and succeed
    import time; time.sleep(0.11)
    assert cb.call(lambda: "ok")=="ok"