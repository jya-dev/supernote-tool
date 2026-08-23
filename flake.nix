{
    description = "Unofficial python tool for Ratta Supernote";

    inputs = {
        nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
        flake-utils.url = "github:numtide/flake-utils";
    };

    outputs =
        {
            self,
            nixpkgs,
            flake-utils,
        }:
        flake-utils.lib.eachDefaultSystem (
            system:
            let
                pkgs = import nixpkgs { inherit system; };
                python = pkgs.python3;

                potracer = python.pkgs.buildPythonPackage rec {
                    pname = "potracer";
                    version = "0.0.1";
                    format = "setuptools";

                    src = python.pkgs.fetchPypi {
                        inherit pname version;
                        sha256 = "057wz5368nfwklaajdcc738x983978ash8xqnf9b378m614vgf9c";
                    };

                    propagatedBuildInputs = with python.pkgs; [
                        numpy
                    ];

                    doCheck = false;
                };

                supernote-tool = python.pkgs.buildPythonApplication rec {
                    pname = "supernotelib";
                    version = "0.7.3";
                    pyproject = true;

                    src = ./.;

                    nativeBuildInputs = with python.pkgs; [
                        hatchling
                    ];

                    propagatedBuildInputs = with python.pkgs; [
                        colour
                        fusepy
                        numpy
                        pillow
                        potracer
                        pypng
                        reportlab
                        svglib
                        svgwrite
                    ];

                    doCheck = false;
                };
            in
            {
                packages.default = supernote-tool;
                packages.supernote-tool = supernote-tool;

                apps.default = {
                    type = "app";
                    program = "${supernote-tool}/bin/supernote-tool";
                };

                apps.supernote-fuse = {
                    type = "app";
                    program = "${supernote-tool}/bin/supernote-fuse";
                };

                devShells.default = pkgs.mkShell {
                    inputsFrom = [ supernote-tool ];
                };
            }
        );
}
