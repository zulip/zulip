class zulip::builder {
  class { 'zulip::base': }

  $buildd_packages = [
    "apt-spy",
    "netselect-apt",
    "ubuntu-dev-tools",
    "schroot",
    "sbuild",
    ]
  package { $buildd_packages: ensure => "installed" }

  file { "/home/zulip/.sbuildrc":
    require => Package[sbuild],
    ensure => file,
    owner  => "humbug",
    group  => "humbug",
    mode => 644,
    source => "puppet:///modules/zulip/builder/sbuildrc",
  }

  file { "/usr/share/keyrings/ubuntu-archive-keyring.gpg":
    ensure => file,
    mode => 644,
    source => "puppet:///modules/zulip/builder/ubuntu-archive-keyring.gpg",
  }


  file { "/root/.sbuildrc":
    ensure => 'link',
    target => '/home/zulip/.sbuildrc',
  }

  exec { "adduser root sbuild": }
  exec { "adduser humbug sbuild": }
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


}
