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

print("Python plugin loaded!")
