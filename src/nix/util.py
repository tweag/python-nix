from __future__ import annotations

import typing
from typing import TypeAlias, TypeVar, Optional, Callable, Any
from typing import Concatenate, ParamSpec

from ._nix_api_util import lib, ffi

CData: TypeAlias = ffi.CData

R = TypeVar("R")
P = ParamSpec("P")


class Context:
    def __init__(self) -> None:
        self._ctx = ffi.gc(lib.nix_c_context_create(), lib.nix_c_context_free)

    def nix_err_msg(self) -> str:
        with Ctx() as ctx:
            msg = ctx.check(lib.nix_err_msg, self._ctx, ffi.NULL)
        return ffi.string(msg).decode("utf-8", errors="replace")

    def nix_err_code(self) -> int:
        """read error code directly"""
        return typing.cast(int, ffi.cast("nix_err*", self._ctx)[0])

    def nix_err_name(self) -> str:
        value = ffi.new("char[128]")
        with Ctx() as ctx:
            ctx.check(lib.nix_err_name, self._ctx, value, len(value))
        return ffi.string(value).decode("utf-8", errors="replace")

    def nix_err_info_msg(self) -> str:
        value = ffi.new("char[1024]")
        with Ctx() as ctx:
            ctx.check(lib.nix_err_info_msg, self._ctx, value, len(value))
        return ffi.string(value).decode()

    def check(
        self,
        fn: Callable[Concatenate[ffi.CData, P], R],
        *rest: P.args,
        **kwrest: P.kwargs,
    ) -> R:
        res = fn(self._ctx, *rest, **kwrest)
        self._err_check(self.nix_err_code())
        return res

    def _err_check(self, err_code: int) -> None:
        match err_code:
            case lib.NIX_OK:
                return
            case lib.NIX_ERR_NIX_ERROR:
                name = self.nix_err_name()
                if name in ERR_MAP:
                    err = ERR_MAP[name](self.nix_err_msg())
                else:
                    err = NixError(self.nix_err_msg())
                    err.name = name
                    err.msg = self.nix_err_info_msg()
                raise err
            case lib.NIX_ERR_KEY:
                raise KeyError(self.nix_err_msg())
            case lib.NIX_ERR_UNKNOWN:
                raise NixAPIError(self.nix_err_msg())
            case _:
                raise RuntimeError(self.nix_err_msg())


class NixAPIError(Exception):
    """ Any Nix error """
    pass


class NixError(NixAPIError):
    """ represents a named nix error """
    msg: Optional[str]
    name: Optional[str]


class ThrownError(NixError):
    """ error from builtins.throw """
    def __repr__(self) -> str:
        if self.msg:
            return 'ThrownError("' + self.msg + '")'
        else:
            return super().__repr__()


class AssertionError(NixError):
    """ assert failure """
    pass


ERR_MAP = {"nix::ThrownError": ThrownError, "nix::AssertionError": AssertionError}


class Settings:
    """ Wrapper for Nix settings. Globally exposed as 'nix.util.settings' """
    def __init__(self) -> None:
        pass

    def __setitem__(self, key: str, value: str) -> None:
        """ Set a Nix setting """
        with Ctx() as ctx:
            ctx.check(lib.nix_setting_set, key.encode(), value.encode())

    def __getitem__(self, key: str) -> str:
        """ Retrieve Nix setting """
        value = ffi.new("char[1024]")
        with Ctx() as ctx:
            ctx.check(lib.nix_setting_get, key.encode(), value, len(value))
        return ffi.string(value).decode()


class Ctx:
    err_contexts: list[Context] = []
    ctx_level: int = 0

    def __enter__(self) -> Context:
        Ctx.ctx_level += 1
        if len(Ctx.err_contexts) < Ctx.ctx_level:
            Ctx.err_contexts.append(Context())
        return Ctx.err_contexts[Ctx.ctx_level - 1]

    def __exit__(self, type: Any, value: Any, traceback: Any) -> None:
        Ctx.ctx_level -= 1


# settings
settings = Settings()

version = ffi.string(lib.nix_version_get()).decode()


def nix_util_init() -> None:
    with Ctx() as ctx:
        ctx.check(lib.nix_libutil_init)
