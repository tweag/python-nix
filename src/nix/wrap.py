from __future__ import annotations

import typing
import re

from collections.abc import Callable
from typing import Any, Concatenate

from .util import Ctx, CData

if typing.TYPE_CHECKING:
    from ._nix_api_types import Lib


P = typing.ParamSpec("P")


def wrap_ffi(
    f: Callable[Concatenate[CData, P], Any] | Callable[P, Any] | int
) -> Callable[P, Any] | int:
    """Wrap an ffi.lib member for nix error checking"""
    if isinstance(f, int):
        return f

    if not f.__doc__:
        raise TypeError("couldn't parse to-be-wrapped function")

    # todo: should we parse the signature?
    sig = f.__doc__.split("\n")[0]
    func, argstr = sig.split("(", 1)
    mtch = re.match(r"((struct )?[a-zA-Z0-9_]+[ \*]*)", func)
    if not mtch:
        raise RuntimeError("invalid function sig " + sig)
    tp = mtch[0].strip()
    if tp == "void":
        return typing.cast(Callable[P, Any], f)

    # f is foo something(nix_context*, ...)
    g = typing.cast(Callable[Concatenate[CData, P], Any], f)

    def wrap_null(*args: P.args, **kwargs: P.kwargs) -> Any:
        with Ctx() as ctx:
            return ctx.check(g, *args, **kwargs)

    return wrap_null


class LibWrap:
    """Wrap an ffi.lib for nix error checking"""

    def __init__(self, thing: Lib):
        self._thing = thing

    def __getattr__(self, attr: str) -> Any:
        r: Any = wrap_ffi(getattr(self._thing, attr))
        setattr(self, attr, r)
        return r

    def __dir__(self) -> list[str]:
        return dir(self._thing)
