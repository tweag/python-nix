# Python bindings for Nix using CFFI
Maintainer status: maintained, experimental
Compatibility: Requires C API

# Example
```python
import nix
pkgs = nix.eval("import nixpkgs")({})
hello2 = pkgs["hello"]["overrideAttrs"](lambda o: {
  "pname": str(o["pname"]) + "-test"
})
hello2.build()
```
