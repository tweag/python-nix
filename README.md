# Python bindings for Nix using CFFI
Maintainer status: maintained, experimental
Compatibility: Requires https://github.com/NixOS/nix/pull/8699


# Getting started
```shell
$ nix develop tweag/python-nix#env
$ python
>>> import nix
>>> nix.eval("1+1")
<Nix: 2>
>>>
```

# Hacking
```shell
$ nix develop .#
$ cd src
$ python buildFFI.py
$ python
>>> import nix
```

# Example
```python
import nix
pkgs = nix.eval("import nixpkgs")({})
hello2 = pkgs["hello"]["overrideAttrs"](lambda o: {
  "pname": str(o["pname"]) + "-test"
})
hello2.build()
```
