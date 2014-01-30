# Class: apt::unattended_upgrades
#
# This class manages the unattended-upgrades package and related configuration
# files for ubuntu
#
# origins are the repositories to automatically upgrade included packages
# blacklist is a list of packages to not automatically upgrade
# update is how often to run "apt-get update" in days
# download is how often to run "apt-get upgrade --download-only" in days
# upgrade is how often to upgrade packages included in the origins list in days
# autoclean is how often to run "apt-get autoclean" in days
#
# information on the other options can be found in the 50unattended-upgrades
# file and in /etc/cron.daily/apt
#
class apt::unattended_upgrades (
  $origins = ['${distro_id}:${distro_codename}-security'],
  $blacklist = [],
  $update = "1",
  $download = "1",
  $upgrade = "1",
  $autoclean = "7",
  $auto_fix = true,
  $minimal_steps = false,
  $install_on_shutdown = false,
  $mail_to = "NONE",
  $mail_only_on_error = false,
  $remove_unused = true,
  $auto_reboot = false,
  $dl_limit = "NONE",
  $enable = "1",
  $backup_interval = "0",
  $backup_level = "3",
  $max_age = "0",
  $min_age = "0",
  $max_size = "0",
  $download_delta = "0",
  $verbose = "0",
) {

  validate_bool(
    $auto_fix,
    $minimal_steps,
    $install_on_shutdown,
    $mail_only_on_error,
    $remove_unused,
    $auto_reboot
  )

  package { 'unattended-upgrades':
    ensure => present,
  }

  File {
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    require => Package['unattended-upgrades'],
  }

  file {
    '/etc/apt/apt.conf.d/50unattended-upgrades':
      content => template('apt/50unattended-upgrades.erb');
    '/etc/apt/apt.conf.d/10periodic':
      content => template('apt/10periodic.erb');
  }
}
