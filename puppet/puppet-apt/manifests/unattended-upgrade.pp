class apt::unattended-upgrade {
  package {'unattended-upgrades':
    ensure => present,
  }
}
