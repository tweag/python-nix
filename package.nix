{ buildPythonPackage, cffi, nix, pkgconfig, lib }:
buildPythonPackage {
  pname = "python-nix";
  version = "0.0.1";
  format = "setuptools";
  src = ./.;
  propagatedBuildInputs = [ cffi ];
  buildInputs = [ nix ];
  nativeBuildInputs = [
    pkgconfig # is a python package
  ];
  pythonImportsCheck = [ "nix" "nix.util" "nix.store" "nix.expr" ];
  meta = with lib; {
    homepage = "https://github.com/tweag/python-nix";
    description = "Python Nix FFI";
    license = licenses.mit;
    maintainers = [ maintainers.yorickvp ];
  };
}
