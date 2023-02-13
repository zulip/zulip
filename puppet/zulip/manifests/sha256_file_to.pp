# @summary Downloads, verifies hash, and copies the one file out.
#
define zulip::sha256_file_to(
  String $sha256,
  String $url,
  String $install_to,
) {
  exec { $url:
    command => "${::zulip_scripts_path}/setup/sha256-file-to ${sha256} ${url} ${install_to}",
    creates => $install_to,
    timeout => 600,
  }
}
