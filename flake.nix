{
  inputs.nix = { url = "github:tweag/nix/nix-c-bindings"; };
  inputs.nixpkgs.follows = "nix/nixpkgs";
  outputs = { self, nix, nixpkgs, flake-utils, ... }:
    let pkgs = nixpkgs.legacyPackages.x86_64-linux;
    in {
      devShells.x86_64-linux.default = pkgs.mkShell {
        buildInputs = [
          (pkgs.python3.withPackages
            (p: [ p.cffi p.pkgconfig p.setuptools p.build p.sphinx ]))
          nix.packages.x86_64-linux.default
          pkgs.pkg-config
          pkgs.ruff
          pkgs.black
        ];
      };
    };
}
