# @summary Outgoing HTTP CONNECT proxy for HTTP/HTTPS on port 4750.
#
class zulip::profile::smokescreen {
  include zulip::profile::base
  include zulip::supervisor

  $golang_version = '1.14.10'
  zulip::sha256_tarball_to { 'golang':
    url     => "https://golang.org/dl/go${golang_version}.linux-amd64.tar.gz",
    sha256  => '66eb6858f375731ba07b0b33f5c813b141a81253e7e74071eec3ae85e9b37098',
    install => {
      'go/' => "/srv/golang-${golang_version}/",
    },
  }
  file { '/srv/golang':
    ensure  => 'link',
    target  => "/srv/golang-${golang_version}/",
    require => Zulip::Sha256_tarball_to['golang'],
  }

  $version = '0.0.2'
  zulip::sha256_tarball_to { 'smokescreen':
    url     => "https://github.com/stripe/smokescreen/archive/v${version}.tar.gz",
    sha256  => '7255744f89a62a103fde97d28e3586644d30191b4e3d1f62c9a99e13d732a012',
    install => {
      "smokescreen-${version}/" => "/srv/smokescreen-src-${version}/",
    },
  }
  exec { 'compile smokescreen':
    command     => "/srv/golang/bin/go build -o /usr/local/bin/smokescreen-${version}",
    cwd         => "/srv/smokescreen-src-${version}/",
    # GOCACHE is required; nothing is written to GOPATH, but it is required to be set
    environment => ['GOCACHE=/tmp/gocache', 'GOPATH=/root/go'],
    creates     => "/usr/local/bin/smokescreen-${version}",
    require     => [Zulip::Sha256_tarball_to['golang'], Zulip::Sha256_tarball_to['smokescreen']],
  }

  file { '/usr/local/bin/smokescreen':
    ensure  => 'link',
    target  => "/usr/local/bin/smokescreen-${version}",
    require => Exec['compile smokescreen'],
    notify  => Service[supervisor],
  }

  file { '/etc/supervisor/conf.d/zulip/smokescreen.conf':
    ensure  => file,
    require => [
      Package[supervisor],
      File['/usr/local/bin/smokescreen'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/supervisor/smokescreen.conf.erb'),
    notify  => Service[supervisor],
  }
  # Removed 2021-03 in version 4.0; these lines can be removed in
  # Zulip version 5.0 and later.
  file { '/etc/supervisor/conf.d/smokescreen.conf':
    ensure  => absent,
  }
}
