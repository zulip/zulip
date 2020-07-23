# @summary Observability using Grafana
#
class zulip_ops::profile::grafana {
  include zulip_ops::profile::base
  include zulip::supervisor

  $version = '8.0.0'
  zulip::sha256_tarball_to { 'grafana':
    url     => "https://dl.grafana.com/oss/release/grafana-${version}.linux-amd64.tar.gz",
    sha256  => '6f006990fcb89307e7911b0b3a4b54810c7e4a6f16240d9deb979f3010a71a9e',
    install => {
      "grafana-${version}/" => "/srv/grafana-${version}/",
    },
  }
  file { '/srv/grafana':
    ensure  => 'link',
    target  => "/srv/grafana-${version}/",
    require => Zulip::Sha256_tarball_to['grafana'],
  }

  group { 'grafana':
    ensure => present,
    gid    => '1070',
  }
  user { 'grafana':
    ensure     => present,
    uid        => '1070',
    gid        => '1070',
    shell      => '/bin/bash',
    home       => '/srv/grafana',
    managehome => false,
  }
  file { '/var/lib/grafana':
    ensure  => directory,
    owner   => 'grafana',
    group   => 'grafana',
    require => [ User[grafana], Group[grafana] ],
  }
  file { '/var/log/grafana':
    ensure => directory,
    owner  => 'grafana',
    group  => 'grafana',
  }

  zulip_ops::teleport::application { 'monitoring': port => '3000' }
  zulip_ops::firewall_allow { 'grafana': port => '3000' }
  file { '/etc/supervisor/conf.d/grafana.conf':
    ensure  => file,
    require => [
      Package[supervisor],
      File['/srv/grafana'],
      File['/var/lib/grafana'],
      File['/var/log/grafana'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/supervisor/conf.d/grafana.conf',
    notify  => Service[supervisor],
  }

  file { '/etc/grafana':
    ensure => directory,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
  }
  file { '/etc/grafana/grafana.ini':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/grafana/grafana.ini',
    notify => Service[supervisor],
  }
}
