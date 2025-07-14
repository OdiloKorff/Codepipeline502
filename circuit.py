"""Circuit Breaker primitive (Hystrix-like)."""
from __future__ import annotations
import time
import threading
import logging
from enum import Enum, auto
from typing import Callable, TypeVar, Any

_T=TypeVar("_T")
_log=get_logger(__name__)

class _State(Enum):
    CLOSED=auto()
    OPEN=auto()
    HALF_OPEN=auto()

class CircuitBreaker:
    def __init__(self,
                 fail_max:int=5,
                 reset_timeout:float=30.0):
        self.fail_max=fail_max
        self.reset_timeout=reset_timeout
        self._state=_State.CLOSED
        self._failure_count=0
        self._opened_at:float|None=None
        self._lock=threading.Lock()

    def _transition(self,_state:_State):
        _log.debug("Circuit transition %s -> %s",self._state,_state)
        self._state=_state
        if _state==_State.OPEN:
            self._opened_at=time.time()
        elif _state==_State.CLOSED:
            self._failure_count=0
            self._opened_at=None

    def call(self, func:Callable[...,_T], *args:Any, **kwargs:Any)->_T:
        with self._lock:
            if self._state==_State.OPEN:
                if time.time()- (self._opened_at or 0) >= self.reset_timeout:
                    self._transition(_State.HALF_OPEN)
                else:
                    raise RuntimeError("Circuit open – rejecting call")

        try:
            result=func(*args,**kwargs)
        except Exception as exc:
            with self._lock:
                self._failure_count+=1
                if self._failure_count>=self.fail_max:
                    self._transition(_State.OPEN)
            raise
        else:
            with self._lock:
                if self._state==_State.HALF_OPEN:
                    self._transition(_State.CLOSED)
            return result

# global breaker instance for provider broker
GLOBAL_BREAKER=CircuitBreaker(
    fail_max=int(os.getenv("CB_FAIL_MAX", "5")),
    reset_timeout=float(os.getenv("CB_RESET_TIMEOUT", "30"))
)