{
  description = "pygls: The Generic Language Server Framework";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, utils }:

    utils.lib.eachDefaultSystem(system:
      let
        pkgs = import nixpkgs { inherit system; };
        python-wasi = pkgs.callPackage ./nix/python-wasi.nix {};
        # TODO: Perhaps an overlay would allow callPackage to know what python-wasi is.
        python = pkgs.callPackage ./nix/python.nix { python-wasi = python-wasi; };
      in {

        devShells.default = pkgs.mkShell {
          name = "wasi";

          packages = [
            python # -wasi

            pkgs.python311
            pkgs.python311Packages.pytest
            pkgs.python311Packages.pytest-asyncio
            pkgs.python311Packages.pip
          ];
        };
      }
    );
}
