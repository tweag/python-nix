# Python bindings for Nix using CFFI

Maintainer status: maintained, experimental.

Compatibility: Requires https://github.com/NixOS/nix/pull/8699

## Try in a REPL!

```shell
$ nix develop tweag/python-nix#env
$ python
>>> import nix
>>> nix.eval("1+1")
<Nix: 2>
```

## Add to your project

Because this package uses CFFI, it requires a bit more setup than a typical Python package.

To install this package, you will need:
* gcc
* pkg-config

and a specific branch of Nix from https://github.com/NixOS/nix/pull/8699 that can be caught by pkg-config.

You can build it and give it to pkg-config by running:

```shell
$ export PKG_CONFIG_PATH="$(nix build github:tweag/nix/nix-c-bindings#default.dev --no-link --print-out-paths)/lib/pkgconfig"
```

You can install using pip:

```shell
$ pip install git+https://github.com/tweag/python-nix.git
```

## Example

```python
import nix

# Load the nixpkgs repository
pkgs = nix.eval("import nixpkgs")({})

# Get the hello package and override its name
hello2 = pkgs["hello"]["overrideAttrs"](lambda o: {
  "pname": str(o["pname"]) + "-test"
})

# Build the package
hello2.build()
```

## Development

### Using Nix

A development environment is available in the provided Nix flake.
Once in the development environment, run `buildFFI.py` to test your changes.

```shell
$ nix develop .#
$ cd src
$ python buildFFI.py
$ python
>>> import nix
```
