# @summary Outgoing HTTP CONNECT proxy for HTTP/HTTPS on port 4750.
#
class zulip::profile::smokescreen {
  include zulip::profile::base
  include zulip::supervisor

  $golang_version = '1.17'
  zulip::sha256_tarball_to { 'golang':
    url     => "https://golang.org/dl/go${golang_version}.linux-amd64.tar.gz",
    sha256  => '6bf89fc4f5ad763871cf7eac80a2d594492de7a818303283f1366a7f6a30372d',
    install => {
      'go/' => "/srv/golang-${golang_version}/",
    },
  }
  file { '/srv/golang':
    ensure  => 'link',
    target  => "/srv/golang-${golang_version}/",
    require => Zulip::Sha256_tarball_to['golang'],
  }

  $version = 'dc403015f563eadc556a61870c6ad327688abe88'
  zulip::sha256_tarball_to { 'smokescreen':
    url     => "https://github.com/stripe/smokescreen/archive/${version}.tar.gz",
    sha256  => 'ad4b181d14adcd9425045152b903a343dbbcfcad3c1e7625d2c65d1d50e1959d',
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

  $listen_address = zulipconf('http_proxy', 'listen_address', '127.0.0.1')
  file { "${zulip::common::supervisor_conf_dir}/smokescreen.conf":
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
}
