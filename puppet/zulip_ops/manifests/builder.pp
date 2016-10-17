class zulip_ops::builder {
  include zulip_ops::base

  $buildd_packages = [
    # Useful tools for packaging
    "apt-spy",
    "netselect-apt",
    # Packages needed to do the builds
    "ubuntu-dev-tools",
    "schroot",
    "sbuild",
    ]
  package { $buildd_packages: ensure => "installed" }

  file { "/home/zulip/.sbuildrc":
    require => Package[sbuild],
    ensure => file,
    owner  => "zulip",
    group  => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_ops/builder/sbuildrc",
  }

  file { "/usr/share/keyrings/ubuntu-archive-keyring.gpg":
    ensure => file,
    mode => 644,
    source => "puppet:///modules/zulip_ops/builder/ubuntu-archive-keyring.gpg",
  }


  file { "/root/.sbuildrc":
    ensure => 'link',
    target => '/home/zulip/.sbuildrc',
  }

  exec { "adduser root sbuild": }
  exec { "adduser zulip sbuild": }
  chroot { "precise":
    distro => "ubuntu",
    ensure => present,
  }
  chroot { "quantal":
    distro => "ubuntu",
    ensure => present,
  }
  chroot { "raring":
    distro => "ubuntu",
    ensure => present,
  }
  chroot { "stable":
    distro => "debian",
    ensure => present,
  }
  chroot { "testing":
    distro => "debian",
    ensure => present,
  }
  chroot { "unstable":
    distro => "debian",
    ensure => present,
  }


}
