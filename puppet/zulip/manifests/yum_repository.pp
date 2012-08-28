class zulip::yum_repository {
  $setup_yum_repo_file = "${facts['zulip_scripts_path']}/lib/setup-yum-repo"
  exec{'setup_yum_repo':
    command => "bash -c '${setup_yum_repo_file} --prod'",
  }
}
