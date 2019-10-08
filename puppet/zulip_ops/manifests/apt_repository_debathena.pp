class zulip_ops::apt_repository_debathena {
  $setup_file = "${::scripts_path}/lib/setup-apt-repo-debathena"
  exec { 'setup_apt_repo_debathena':
    command => "bash -c '${setup_file}'",
  }
}
