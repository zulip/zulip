# @summary Outgoing HTTP CONNECT proxy for HTTP/HTTPS on port 4750.
#
class zulip::profile::smokescreen {
  include zulip::profile::base
  include zulip::supervisor

  $golang_version = '1.16.4'
  zulip::sha256_tarball_to { 'golang':
    url     => "https://golang.org/dl/go${golang_version}.linux-amd64.tar.gz",
    sha256  => '7154e88f5a8047aad4b80ebace58a059e36e7e2e4eb3b383127a28c711b4ff59',
    install => {
      'go/' => "/srv/golang-${golang_version}/",
    },
  }
  file { '/srv/golang':
    ensure  => 'link',
    target  => "/srv/golang-${golang_version}/",
    require => Zulip::Sha256_tarball_to['golang'],
  }

  $version = 'bfca45c5e61f3587eaaf1dcc89a0c4116501cba3'
  zulip::sha256_tarball_to { 'smokescreen':
    url     => "https://github.com/stripe/smokescreen/archive/${version}.tar.gz",
    sha256  => '7aa2719abd282930b01394e5e748885a8e8cb8121fe97a15446f93623ec13f59',
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
