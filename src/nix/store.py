from __future__ import annotations

from typing import TypeAlias, Optional

from ._nix_api_store import ffi, lib as lib_unwrapped
from .wrap import LibWrap

lib = LibWrap(lib_unwrapped)

CData: TypeAlias = ffi.CData


class StorePath:
    """ A path pointing to the Nix store """
    def __init__(self, ptr: ffi.CData) -> None:
        self._path = ptr


class Store:
    """ A Nix Store """
    def __init__(
        self, url: Optional[str] = None, params: Optional[dict[str, str]] = None
    ) -> None:
        """ Open a Nix Store """
        ffi.init_once(lib.nix_libstore_init, "init_libstore")
        url_c = ffi.NULL
        params_c = ffi.NULL
        if url is not None:
            url_c = ffi.new("char[]", url.encode())
        # store references because they have ownership
        pm = []
        kvs = []
        if params is not None:
            for k, v in params.items():
                kv = [ffi.new("char[]", k.encode()), ffi.new("char[]", v.encode())]
                kvs.append(kv)
                pm.append(ffi.new("char*[]", kv))
            pm.append(ffi.NULL)
            params_c = ffi.new("char**[]", pm)
        self._store = ffi.gc(lib.nix_store_open(url_c, params_c), lib.nix_store_unref)

    def get_uri(self) -> str:
        """ Get the URI of the Nix store """
        dest = ffi.new("char[256]")
        lib.nix_store_get_uri(self._store, dest, len(dest))
        return ffi.string(dest).decode()

    def get_version(self) -> str:
        """ Get the version of the remote Nix store, or throw an error if the remote nix store has no version. """
        dest = ffi.new("char[256]")
        lib.nix_store_get_version(self._store, dest, len(dest))
        return ffi.string(dest).decode()

    def parse_path(self, path: str) -> StorePath:
        """ Parse a /nix/store path into a StorePath """
        path_ct = ffi.new("char[]", path.encode())
        sp = lib.nix_store_parse_path(self._store, path_ct)
        return StorePath(ffi.gc(sp, lib.nix_store_path_free))

    def _ensure_store_path(self, path: StorePath | str) -> StorePath:
        if isinstance(path, StorePath):
            return path
        if isinstance(path, str):
            return self.parse_path(path)
        # value
        # if value is string: storepath(str)
        if "type" in path and str(path["type"]) == "derivation":
            return self.parse_path(str(path["drvPath"]))

    def is_valid_path(self, path: StorePath | str) -> bool:
        """ Check if a Nix path (and all its dependents) exists in the store """
        return bool(
            lib.nix_store_is_valid_path(
                self._store, self._ensure_store_path(path)._path
            )
        )

    def build(self, path: StorePath | str) -> dict[str, str]:
        """ Ensure that a Nix store path is valid """
        path = self._ensure_store_path(path)
        res = {}

        # todo extern "Python"
        @ffi.callback("void(void*, char*, char*)")
        def iter_callback(userdata: CData, key: CData, path: CData) -> None:
            res[ffi.string(key).decode()] = ffi.string(path).decode()

        lib.nix_store_build(self._store, path._path, ffi.NULL, iter_callback)
        return res
