# @summary Observability using Grafana
#
class zulip_ops::profile::grafana {
  include zulip_ops::profile::base
  include zulip::supervisor

  $version = '8.3.2'
  $dir = "/srv/zulip-grafana-${version}/"
  $bin = "${dir}bin/grafana-server"

  zulip::external_dep { 'grafana':
    version        => $version,
    url            => "https://dl.grafana.com/oss/release/grafana-${version}.linux-${::architecture}.tar.gz",
    sha256         => '100f92c50aa612f213052c55594e58b68b7da641b751c5f144003d704730d189',
    tarball_prefix => "grafana-${version}/",
    bin            => 'bin/grafana-server',
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
    home       => $dir,
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
  file { "${zulip::common::supervisor_conf_dir}/grafana.conf":
    ensure  => file,
    require => [
      Package[supervisor],
      File[$bin],
      File['/var/lib/grafana'],
      File['/var/log/grafana'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/supervisor/conf.d/grafana.conf.erb'),
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
