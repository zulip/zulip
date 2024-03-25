class zulip::apt_repository {
  $setup_apt_repo_file = "${facts['zulip_scripts_path']}/lib/setup-apt-repo"
  exec{'setup_apt_repo':
    command => "bash -c '${setup_apt_repo_file}'",
    unless  => "bash -c '${setup_apt_repo_file} --verify'",
  }
}
