{
  description = "Python-Nix interop";
  inputs = {
    nix.url = "github:tweag/nix/nix-c-bindings";
    nixpkgs.follows = "nix/nixpkgs";
  };
  outputs = { self, nix, nixpkgs, flake-utils, ... }@inputs:
    let systems = builtins.attrNames nix.packages;
    in flake-utils.lib.eachSystem systems (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        nix = inputs.nix.packages.${system}.default;
        inherit (pkgs) python3;
      in {
        devShells.env = pkgs.mkShell {
          buildInputs = [ nix (python3.withPackages (_: [self.packages.${system}.default])) ];
        };
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            (python3.withPackages
              (p: [ p.cffi p.pkgconfig p.setuptools p.build p.sphinx ]))
            nix # from flake input
            pkg-config
            ruff
            black
            mypy
          ];
        };
        packages.default =
          python3.pkgs.callPackage ./package.nix { inherit nix; };
      });
}
