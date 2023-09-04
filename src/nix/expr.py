from __future__ import annotations

import collections.abc
import typing
from collections.abc import Callable, Iterator
from typing import Any, TypeAlias, Union, Optional
import enum
import inspect
from threading import local as thread_local
from pathlib import PurePath

from .util import settings, NixAPIError
from .store import Store
from .expr_util import ffi, lib, lib_unwrapped, CData, ReferenceGC
from .external import ExternalValue

__all__ = ["ExternalValue", "State", "Value", "Type", "Function", "PrimOp"]


class State:
    """ A Nix interpreter State """
    def __init__(self, search_path: list[str], store_wrapper: Store) -> None:
        ffi.init_once(lib.nix_libexpr_init, "init_libexpr")
        search_path_c = [ffi.new("char[]", path.encode()) for path in search_path]
        search_path_c.append(ffi.NULL)
        search_path_ptr = ffi.new("char*[]", search_path_c)
        self._state = ffi.gc(
            lib.nix_state_create(search_path_ptr, store_wrapper._store),
            lib.nix_state_free,
        )

    def eval_string(self, expr_string: str, path: str) -> Value:
        """ Evaluate a Nix expression string into a Value """
        val = self.alloc_val()
        expr = lib.nix_expr_eval_from_string(
            self._state, expr_string.encode(), path.encode(), val._value
        )
        return val

    def alloc_val(self) -> Value:
        """ Allocate an empty Value. Will crash when accessing without setting a value """
        return Value(self._state)

    def val_from_python(self, py_val: Evaluated) -> Value:
        """ Create a Nix value from a Python value """
        v = self.alloc_val()
        v.set(py_val)
        return v


Evaluated: TypeAlias = Union[
    int,
    float,
    str,
    None,
    dict,
    list,
    PurePath,
    "Function",  # | String
    "ExternalValue",
]
DeepEvaluated = Union[
    int,
    float,
    str,
    None,
    dict[str, "DeepEvaluated"],
    list["DeepEvaluated"],
    PurePath,
    "Function",
    "ExternalValue",
    # string
]


class Type(enum.Enum):
    thunk = lib.NIX_TYPE_THUNK
    int = lib.NIX_TYPE_INT
    float = lib.NIX_TYPE_FLOAT
    bool = lib.NIX_TYPE_BOOL
    string = lib.NIX_TYPE_STRING
    path = lib.NIX_TYPE_PATH
    null = lib.NIX_TYPE_NULL
    attrs = lib.NIX_TYPE_ATTRS
    list = lib.NIX_TYPE_LIST
    function = lib.NIX_TYPE_FUNCTION
    external = lib.NIX_TYPE_EXTERNAL


evaluated_types = {
    Type.int,
    Type.float,
    Type.bool,
    Type.string,
    Type.path,
    Type.null,
    Type.attrs,
    Type.list,
    Type.function,
    Type.external,
}


class Function:
    def __init__(self, val: Value) -> None:
        self.value = val

    def __repr__(self) -> str:
        return repr(self.value)

    def __call__(self, arg: Value | Evaluated) -> Value:
        if not isinstance(arg, Value):
            arg2 = Value(self.value._state)
            arg2.set(arg)
            arg = arg2
        res = Value(self.value._state)
        lib.nix_value_call(
            self.value._state,
            self.value._value,
            arg._value,
            res._value,
        )
        return res


T = typing.TypeVar("T")


# all primops use this code. first argument is secretly the primop handle
@ffi.def_extern()
def py_nix_primop_base(user_data: CData, c_ctx: CData, st: CData, args: CData, ret: CData) -> None:
    result = Value(st, ret, make_reference=True)
    PrimOp.calling_state.state = st
    try:
        op = ffi.from_handle(user_data)
        assert type(op) is PrimOp
        argv = []
        for i in range(op.arity):
            argv.append(Value(st, args[i], make_reference=True))
        res = op.func(*argv)
        result.set(res)
    except Exception as e:
        print("Error in callback")
        print(e)
        lib_unwrapped.nix_set_err_msg(c_ctx, lib.NIX_ERR_UNKNOWN, str(e).encode())
        result.set(None)
    finally:
        PrimOp.calling_state.state = None


class PrimOp(ReferenceGC):
    func: Callable[..., Evaluated | Value]
    arity: int
    _docs: CData
    _primop: CData
    handle: CData

    calling_state = thread_local()
    "while inside a primop callback, this contains the interpreter State* pointer at PrimOp.calling_state.state"

    def __init__(self, cb: Callable[..., Evaluated | Value]) -> None:
        ffi.init_once(lib.nix_libexpr_init, "init_libexpr")

        args, varargs, varkw, defaults = inspect.getargspec(cb)
        if varargs is not None or varkw is not None or defaults is not None:
            raise TypeError("only simple methods can be primops now")
        arity = len(args)
        argnames_c = [ffi.new("char[]", path.encode()) for path in args]
        argnames_c.append(ffi.NULL)

        argnames_ptr = ffi.new("char*[]", argnames_c)

        self._docs = (
            ffi.new("char[]", cb.__doc__.encode())
            if cb.__doc__ is not None
            else ffi.NULL
        )

        self.func = cb
        self.arity = arity
        self.handle = ffi.new_handle(self)
        self._primop = lib.nix_alloc_primop(
            lib_unwrapped.py_nix_primop_base,
            arity,
            cb.__name__.encode(),
            argnames_ptr,
            self._docs,
            self.handle
        )
        super().__init__(self._primop)

    def unref(self) -> None:
        lib.nix_gc_decref(self._primop)

class Value:
    """ A Nix Value """
    def __init__(
        self,
        state_ptr: CData,
        value_ptr: CData | None = None,
        make_reference: bool = False,
    ) -> None:
        self._state = state_ptr
        if value_ptr is None:
            self._value = lib.nix_alloc_value(state_ptr)
        else:
            self._value = value_ptr
            if make_reference:
                lib.nix_gc_incref(self._value)

    def __del__(self) -> None:
        lib.nix_gc_decref(self._value)

    def get_type(self) -> Type:
        return Type(lib.nix_get_type(self._value))

    def _force(self, deep: bool = False) -> None:
        if deep:
            lib.nix_value_force_deep(self._state, self._value)
        else:
            lib.nix_value_force(self._state, self._value)

    def __repr__(self) -> str:
        t = self.get_type()
        if t == Type.attrs and "type" in self and self["type"].force() == "derivation":
            return "<Nix derivation {}>".format(self["drvPath"].force())
        elif t not in {Type.thunk, Type.function, Type.attrs}:
            return f"<Nix: {self.force()}>"
        else:
            return f"<Nix Value ({self.get_typename()})>"

    def _to_python(self, deep: bool = False) -> Evaluated:
        match self.get_type():
            case Type.int:
                return int(lib.nix_get_int(self._value))
            case Type.float:
                return float(lib.nix_get_double(self._value))
            case Type.bool:
                return bool(lib.nix_get_bool(self._value))
            case Type.string:
                return ffi.string(lib.nix_get_string(self._value)).decode()
            case Type.attrs:
                res_dict: dict[str, Value | DeepEvaluated] = {}
                if deep:
                    self.get_attr_iterate(
                        lambda k, v: res_dict.__setitem__(k, v._to_python(deep))
                    )
                else:
                    self.get_attr_iterate(lambda k, v: res_dict.__setitem__(k, v))
                return res_dict
            case Type.list:
                res_list: list[Value] = list(self)
                if deep:
                    # todo don't need another force call
                    return [x._to_python(deep=True) for x in res_list]
                return res_list
            case Type.function:
                return Function(self)
            case Type.path:
                return PurePath(
                    ffi.string(lib.nix_get_path_string(self._value)).decode()
                )
            case Type.external:
                ev = lib.nix_get_external(self._value)
                handle = lib.nix_get_external_value_content(ev)
                if handle == ffi.NULL:
                    raise RuntimeError("Unknown external value")
                return ExternalValue.from_handle(handle)
            case Type.null:
                return None
            case _:
                raise NotImplementedError("can't convert", self.get_type())

    # https://github.com/python/mypy/issues/9773
    def force(self, typeCheck: Any = evaluated_types, deep: bool = False) -> Evaluated:
        self.force_type(typeCheck, deep=deep)
        return self._to_python(deep)

    def force_type(
        self, typeCheck: set[Type] | Type = evaluated_types, deep: bool = False
    ) -> Type:
        self._force(deep=deep)
        tp = self.get_type()
        if not isinstance(typeCheck, set):
            typeCheck = {typeCheck}
        if tp not in typeCheck:
            raise TypeError(
                f"nix value is {self.get_typename()} while {str(typeCheck)} was expected"
            )

        return tp

    def get_typename(self) -> str:
        return str(ffi.string(lib.nix_get_typename(self._value)).decode())

    def get_list_byidx(self, ix: int) -> Value:
        value_ptr = lib.nix_get_list_byidx(self._value, ix)
        return Value(self._state, value_ptr)

    def get_attr_byname(self, name: str) -> Value:
        value_ptr = lib.nix_get_attr_byname(self._value, self._state, name.encode())
        return Value(self._state, value_ptr)

    def get_attr_iterate(self, iter_func: Callable[[str, Value], None]) -> None:
        name_ptr = ffi.new("char**")
        for i in range(len(self)):
            val = Value(
                self._state,
                lib.nix_get_attr_byidx(self._value, self._state, i, name_ptr),
            )
            name = ffi.string(name_ptr[0]).decode()
            iter_func(name, val)

    def __iter__(self) -> typing.Any:
        match self.force_type({Type.attrs, Type.list}):
            case Type.list:
                return collections.abc.Sequence.__iter__(
                    typing.cast(collections.abc.Sequence[Value], self)
                )
            case Type.attrs:
                return iter(typing.cast(dict[str, Evaluated], self.force()))

    def __int__(self) -> int:
        return int(
            typing.cast(
                int | float | str, self.force({Type.int, Type.float, Type.string})
            )
        )

    def __str__(self) -> str:
        return str(
            self.force(
                {Type.float, Type.int, Type.string, Type.path, Type.null, Type.external}
            )
        )

    def __float__(self) -> float:
        return float(
            typing.cast(
                int | float | str, self.force({Type.int, Type.float, Type.string})
            )
        )

    def __bool__(self) -> bool:
        match self.force_type():
            case Type.attrs | Type.list:
                return bool(len(self))
            case _:
                return bool(self._to_python())

    def __len__(self) -> int:
        match self.force_type({Type.attrs, Type.list}):
            case Type.attrs:
                return int(lib.nix_get_attrs_size(self._value))
            case Type.list:
                return int(lib.nix_get_list_size(self._value))
            case _:
                raise RuntimeError

    def __contains__(self, i: int | str) -> bool:
        match self.force_type({Type.attrs, Type.list}):
            case Type.attrs:
                assert type(i) == str
                return bool(
                    lib.nix_has_attr_byname(self._value, self._state, i.encode())
                )
            case Type.list:
                return i in list(self)
            case _:
                raise RuntimeError

    def __getitem__(self, i: int | str) -> Value:
        match self.force_type({Type.attrs, Type.list}):
            case Type.attrs:
                if not isinstance(i, str):
                    raise TypeError("key should be a string")
                return self.get_attr_byname(i)
            case Type.list:
                if not isinstance(i, int):
                    raise TypeError("key should be a integer")
                if i >= len(self):
                    raise IndexError("list index out of range")
                return self.get_list_byidx(i % len(self))
            case _:
                raise RuntimeError

    def keys(self) -> Iterator[str]:
        self.force_type(Type.attrs)
        return iter(self)

    def build(self, store: Optional[Store] = None) -> dict[str, str]:
        if store is None:
            from . import _store
            store = _store
        if store is None:
            raise RuntimeError("No known Nix store open, try passing one to .build()")
        self.force_type(Type.attrs)
        if "type" in self and self["type"].force() == "derivation":
            return store.build(str(self["drvPath"]))
        raise TypeError("nix value is not a derivation")

    def __call__(self, arg: Value | Evaluated) -> Value:
        if not isinstance(arg, Value):
            arg2 = Value(self._state)
            arg2.set(arg)
            arg = arg2
        res = Value(self._state)
        lib.nix_value_call(
            self._state,
            self._value,
            arg._value,
            res._value,
        )
        return res

    def set(self, py_val: Value | DeepEvaluated) -> None:
        if isinstance(py_val, Function):
            raise NotImplementedError
        elif isinstance(py_val, Value):
            lib.nix_copy_value(self._value, py_val._value)
        elif isinstance(py_val, bool):
            lib.nix_set_bool(self._value, py_val)
        elif isinstance(py_val, str):
            lib.nix_set_string(self._value, py_val.encode())
        elif isinstance(py_val, float):
            lib.nix_set_double(self._value, py_val)
        elif isinstance(py_val, int):
            lib.nix_set_int(self._value, py_val)
        elif isinstance(py_val, PurePath):
            lib.nix_set_path_string(self._value, str(py_val).encode())
        elif py_val is None:
            lib.nix_set_null(self._value)
        elif isinstance(py_val, ExternalValue):
            lib.nix_set_external(self._value, py_val._ref)
        elif isinstance(py_val, list):
            lib.nix_make_list(self._state, self._value, len(py_val))
            for i in range(len(py_val)):
                v = Value(self._state)
                v.set(py_val[i])
                lib.nix_set_list_byidx(self._value, i, v._value)
        elif isinstance(py_val, dict):
            bb = ffi.gc(
                lib.nix_make_bindings_builder(self._state, len(py_val)),
                lib.nix_bindings_builder_free,
            )
            for k, dv in py_val.items():
                v = Value(self._state)
                v.set(dv)
                lib.nix_bindings_builder_insert(bb, k.encode(), v._value)
            lib.nix_make_attrs(self._value, bb)
        elif callable(py_val):
            # primops will give us a dispatcher, need to call it
            p = PrimOp(py_val)
            lib.nix_set_primop(self._value, p._primop)
            p.unref()
        else:
            raise TypeError("tried to convert unknown type to nix")
