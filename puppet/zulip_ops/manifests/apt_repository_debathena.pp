class zulip_ops::apt_repository_debathena {
  $setup_apt_repo_file = "${::zulip_scripts_path}/lib/setup-apt-repo"
  exec { 'setup_apt_repo_debathena':
    command => "${setup_apt_repo_file} --list zulip_debathena",
    unless  => "${setup_apt_repo_file} --list zulip_debathena --verify",
  }
}
