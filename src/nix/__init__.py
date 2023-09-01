from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .expr import Value

__all__ = ["util", "store", "expr", "eval"]

_state = None
_store = None


def eval(string: str, path: str = ".") -> Value:
    from .store import Store
    from .expr import State

    global _store, _state
    if _store is None or _state is None:
        _store = Store()
        _state = State([], _store)
    return _state.eval_string(string, path)
