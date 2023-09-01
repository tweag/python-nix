from __future__ import annotations

from typing import TypeAlias, Optional

from ._nix_api_expr import ffi, lib as lib_unwrapped
from .wrap import LibWrap

__all__ = ["ffi", "lib", "lib_unwrapped", "ReferenceGC", "GCpin", "CData"]

lib = LibWrap(lib_unwrapped)

CData: TypeAlias = ffi.CData

# keep these alive for the python gc
# todo: weakref?
gc_refs: dict[CData, ReferenceGC] = {}


@ffi.def_extern()
def py_nix_finalizer(obj: CData, client_data: CData) -> None:
    del gc_refs[obj]


class ReferenceGC:
    def __init__(self, obj: CData):
        gc_refs[obj] = self
        lib_unwrapped.nix_gc_register_finalizer(
            obj, ffi.NULL, lib_unwrapped.py_nix_finalizer
        )
