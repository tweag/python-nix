import nix
pkgs = nix.eval("import /home/yorick/nixpkgs { overlays = []; }")

hello = pkgs["hello"]
hello.force()
print(repr(hello))

hello2 = pkgs["hello"]['overrideAttrs'](lambda o: {
    "pname": str(o["pname"]) + "-test"
})
hello2.force()
print(repr(hello2))
print(hello2.build(nix._store))

class Hello:
    def __init__(self):
        self.x = 42
    def hi(self):
        return self.x

test = nix.expr.ExternalValue(Hello())
print(nix.eval('x: x')(test))
