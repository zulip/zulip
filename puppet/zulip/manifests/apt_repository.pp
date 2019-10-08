# This depends on zulip::base having already been evaluated
class zulip::apt_repository {
  $setup_apt_repo_file = "${::zulip_scripts_path}/lib/setup-apt-repo"
  exec{'setup_apt_repo':
    command => "bash -c '${setup_apt_repo_file}'",
  }
}
