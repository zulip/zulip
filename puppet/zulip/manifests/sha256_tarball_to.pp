# @summary Downloads, verifies hash, and copies files out.
#
define zulip::sha256_tarball_to(
  String $sha256,
  String $url,
  Hash[String, String] $install,
) {
  $install_expanded = $install.convert_to(Array).join(' ')
  # Puppet does not support `creates => [...]`, so we have to pick one
  $a_file = $install[keys($install)[0]]
  exec { $url:
    command => "${::zulip_scripts_path}/setup/sha256-tarball-to ${sha256} ${url} ${install_expanded}",
    creates => $a_file,
  }
}
