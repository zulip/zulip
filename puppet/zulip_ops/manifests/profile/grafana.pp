# @summary Observability using Grafana
#
class zulip_ops::profile::grafana {
  include zulip_ops::profile::base
  include zulip::supervisor

  $version = $zulip::common::versions['grafana']['version']
  $dir = "/srv/zulip-grafana-${version}"
  $bin = "${dir}/bin/grafana-server"
  $data_dir = '/var/lib/grafana'

  zulip::external_dep { 'grafana':
    version        => $version,
    url            => "https://dl.grafana.com/oss/release/grafana-${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "grafana-${version}",
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
    home       => $data_dir,
    managehome => false,
  }
  file { $data_dir:
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
      Zulip::External_Dep['grafana'],
      File[$data_dir],
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
    mode   => '0755',
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
