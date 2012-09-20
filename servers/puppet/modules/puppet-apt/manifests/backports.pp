class apt::backports {

  $debian_mirror = 'http://backports.debian.org/debian-backports'
  $ubuntu_mirror = 'http://archive.ubuntu.com/ubuntu'

  $uri = $::operatingsystem ? {
    Debian => "deb ${debian_mirror} ${::lsbdistcodename}-backports main contrib non-free\n",
    Ubuntu => "deb ${ubuntu_mirror} ${::lsbdistcodename}-backports main universe multiverse restricted\n",
  }

  apt::sources_list{'backports':
    ensure  => present,
    content => $uri,
  }

  apt::preferences {"${::lsbdistcodename}-backports":
    ensure   => present,
    package  => '*',
    pin      => "release a=${::lsbdistcodename}-backports",
    priority => 400,
  }

}
