import nix.expr

def pyImport(x):
    mod = __import__(str(x))
    ret = {}
    for key in dir(mod):
        if not key[0] == '_':
            val = getattr(mod, key)
            try:
                v = nix.expr.Value(nix.expr.PrimOp.calling_state.state, make_reference=True)
                v.set(val)
                ret[key] = v
            except Exception as e:
                print(key, "failed:", e)
    return ret

imp = nix.expr.PrimOp(pyImport)
nix.expr.lib.nix_register_primop(imp._primop)



def wrapAsm(fun, store):
    t = fun.type(store)
    arity = len(t.params)
    def arg0(x):
        return fun(store)
    def arg1(x):
        return fun(store, x.force())
    def arg2(x, y):
        return fun(store, x.force(), y.force())
    def arg3(x, y, z):
        return fun(store, x.force(), y.force(), z.force())
    return [arg0, arg1, arg2, arg3][arity]


def wasmImport(x):
    from wasmtime import Store, Module, Instance, WasiConfig, Linker


    store = Store()
    store.set_wasi(WasiConfig())
    linker = Linker(store.engine)
    linker.define_wasi()

    module = Module.from_file(store.engine, str(x))
    instance = linker.instantiate(store, module)
    ret = {}
    for key, func in instance.exports(store)._extern_map.items():
        if key != "memory":
            ret[key] = wrapAsm(func, store)
    return ret

imp2 = nix.expr.PrimOp(wasmImport)
nix.expr.lib.nix_register_primop(imp2._primop)

print("Python plugin loaded!")
