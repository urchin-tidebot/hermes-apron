{
  description = "Hermes Apron development tools; no runtime credentials or services";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      each = f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs { inherit system; }));
    in {
      devShells = each (pkgs: {
        default = pkgs.mkShell {
          packages = with pkgs; [ go uv python314 nodejs_24 chromium ruff gitleaks git gnumake ];
          LD_LIBRARY_PATH = "${pkgs.stdenv.cc.cc.lib}/lib";
          PLAYWRIGHT_NODEJS_PATH = "${pkgs.nodejs_24}/bin/node";
        };
      });
      checks = each (pkgs: {
        source-lint = pkgs.runCommand "hermes-apron-source-lint" {
          nativeBuildInputs = [ pkgs.ruff pkgs.go pkgs.python314 ];
        } ''
          cd ${self}
          ruff check hermes_apron tests tools/*.py __init__.py
          ruff format --check hermes_apron tests tools/*.py __init__.py
          test -z "$(gofmt -l cmd internal)"
          python3 tools/audit.py --source-only
          touch $out
        '';
      });
    };
}
