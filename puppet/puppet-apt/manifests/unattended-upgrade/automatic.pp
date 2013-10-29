class apt::unattended-upgrade::automatic inherits apt::unattended-upgrade {

  apt::conf{'99unattended-upgrade':
    ensure  => present,
    content => "APT::Periodic::Unattended-Upgrade \"1\";\n",
  }

  $dist = $::lsbdistid? {
    Debian  => $::lsbdistcodename,
    default => $::lsbdistid,
  }

  apt::conf{'50unattended-upgrades':
    ensure  => present,
    content => template("apt/unattended-upgrades.${dist}.erb"),
  }

}
