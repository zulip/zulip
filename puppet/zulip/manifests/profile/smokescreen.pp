# @summary Outgoing HTTP CONNECT proxy for HTTP/HTTPS on port 4750.
#
class zulip::profile::smokescreen {
  include zulip::profile::base
  include zulip::supervisor
  include zulip::golang

  $version = 'dc403015f563eadc556a61870c6ad327688abe88'
  zulip::sha256_tarball_to { 'smokescreen':
    url     => "https://github.com/stripe/smokescreen/archive/${version}.tar.gz",
    sha256  => 'ad4b181d14adcd9425045152b903a343dbbcfcad3c1e7625d2c65d1d50e1959d',
    install => {
      "smokescreen-${version}/" => "/srv/zulip-smokescreen-src-${version}/",
    },
  }
  exec { 'compile smokescreen':
    command     => "${zulip::golang::bin} build -o /usr/local/bin/smokescreen-${version}",
    cwd         => "/srv/zulip-smokescreen-src-${version}/",
    # GOCACHE is required; nothing is written to GOPATH, but it is required to be set
    environment => ['GOCACHE=/tmp/gocache', 'GOPATH=/root/go'],
    creates     => "/usr/local/bin/smokescreen-${version}",
    require     => [File[$zulip::golang::bin], Zulip::Sha256_tarball_to['smokescreen']],
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
