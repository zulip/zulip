class kandra::teleport::base {
  include zulip::supervisor

  $setup_apt_repo_file = "${facts['zulip_scripts_path']}/lib/setup-apt-repo"
  exec{ 'setup-apt-repo-teleport':
    command => "${setup_apt_repo_file} --list teleport",
    unless  => "${setup_apt_repo_file} --list teleport --verify",
  }
  package { 'teleport':
    ensure  => installed,
    require => Exec['setup-apt-repo-teleport'],
  }
  service { 'teleport':
    ensure  => stopped,
    enable  => mask,
    require => Package['teleport'],
  }
}
