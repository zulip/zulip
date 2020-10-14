# @summary Outgoing HTTP CONNECT proxy for HTTP/HTTPS on port 4750.
#
class zulip_ops::smokescreen {
  include zulip_ops::base
  include zulip::supervisor

  $golang_version = '1.14.10'
  zulip::sha256_tarball_to { 'golang':
    url     => "https://golang.org/dl/go${golang_version}.linux-amd64.tar.gz",
    sha256  => '66eb6858f375731ba07b0b33f5c813b141a81253e7e74071eec3ae85e9b37098',
    install => {
      'go/' => "/opt/golang-${golang_version}/",
    },
  }
  file { '/opt/golang':
    ensure  => 'link',
    target  => "/opt/golang-${golang_version}/",
    require => Zulip::Sha256_tarball_to['golang'],
  }

  $version = '0.0.2'
  zulip::sha256_tarball_to { 'smokescreen':
    url     => "https://github.com/stripe/smokescreen/archive/v${version}.tar.gz",
    sha256  => '7255744f89a62a103fde97d28e3586644d30191b4e3d1f62c9a99e13d732a012',
    install => {
      "smokescreen-${version}/" => "/opt/smokescreen-src-${version}/",
    },
  }
  exec { 'compile smokescreen':
    command     => "/opt/golang/bin/go build -o /usr/local/bin/smokescreen-${version}",
    cwd         => "/opt/smokescreen-src-${version}/",
    # GOCACHE is required; nothing is written to GOPATH, but it is required to be set
    environment => ['GOCACHE=/tmp/gocache', 'GOPATH=/root/go'],
    creates     => "/usr/local/bin/smokescreen-${version}",
    require     => [Zulip::Sha256_tarball_to['golang'], Zulip::Sha256_tarball_to['smokescreen']],
  }

  file { '/usr/local/bin/smokescreen':
    ensure  => 'link',
    target  => "/usr/local/bin/smokescreen-${version}",
    require => Exec['compile smokescreen'],
  }

  file { '/etc/supervisor/conf.d/smokescreen.conf':
    ensure  => file,
    require => [
      Package[supervisor],
      File['/usr/local/bin/smokescreen'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/supervisor/conf.d/smokescreen.conf',
    notify  => Service[supervisor],
  }
}
