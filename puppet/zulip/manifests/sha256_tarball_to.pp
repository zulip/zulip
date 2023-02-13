# @summary Downloads, verifies hash, and copies files out.
#
define zulip::sha256_tarball_to(
  String $sha256,
  String $url,
  String $install_from,
  String $install_to,
) {
  exec { $url:
    command => "${::zulip_scripts_path}/setup/sha256-tarball-to ${sha256} ${url} ${install_from} ${install_to}",
    creates => $install_to,
    timeout => 600,
  }
}
