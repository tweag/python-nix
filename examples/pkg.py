

def hello(pkgs):
    return pkgs["stdenv"]["mkDerivation"]({
        "name": "hello",
        "src": pkgs["hello"]["src"]
    })
