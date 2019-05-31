{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.vagrant
    pkgs.docker
    pkgs.git
    pkgs.openssh
  ];
}
