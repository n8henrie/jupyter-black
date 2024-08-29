{
  description = "Flake for https://github.com/n8henrie/jupyter-black";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs";
    nixpkgs-stable.url = "github:nixos/nixpkgs/release-23.11";
  };

  outputs =
    {
      self,
      nixpkgs,
      nixpkgs-stable,
    }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-linux"
        "aarch64-linux"
      ];
      eachSystem =
        with nixpkgs.lib;
        f: foldAttrs mergeAttrs { } (map (s: mapAttrs (_: v: { ${s} = v; }) (f s)) systems);
    in
    eachSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ (_: _: { inherit (nixpkgs-stable.legacyPackages.${system}) python38; }) ];
        };
        pname = "jupyter-black";
      in
      {
        packages = {
          default =
            let
              python = pkgs.python312;
            in
            python.withPackages (_: [
              (pkgs.callPackage self.packages.${system}.${pname} {
                inherit (python) python3Packages;
              })
            ]);
          ${pname} =
            { lib, python3Packages }:
            python3Packages.buildPythonPackage {
              inherit pname;
              version = builtins.elemAt (lib.splitString "\"" (
                lib.findSingle (val: builtins.match "^__version__ = \".*\"$" val != null) (abort "none")
                  (abort "multiple")
                  (lib.splitString "\n" (builtins.readFile ./src/${pname}/__init__.py))
              )) 1;

              src = lib.cleanSource ./.;
              pyproject = true;
              nativeBuildInputs = [ python3Packages.setuptools-scm ];
            };
        };

        devShells.default = pkgs.mkShell {
          venvDir = ".venv";
          postVenvCreation = ''
            unset SOURCE_DATE_EPOCH
            pip install -e .[dev,test]
          '';

          buildInputs = with pkgs; [
            python38
            python39
            python310
            python311
            (python312.withPackages (
              ps: with ps; [
                mypy
                playwright
                pytest
                tox
                venvShellHook
              ]
            ))
          ];
        };
      }
    );
}
