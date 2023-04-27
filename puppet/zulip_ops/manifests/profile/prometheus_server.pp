# @summary Gathers Prometheus statistics from all nodes.
#
# Only one instance is necessary.
#
class zulip_ops::profile::prometheus_server {
  include zulip_ops::profile::base
  include zulip_ops::prometheus::base

  # This blackbox monitoring of the backup system runs locally
  include zulip_ops::prometheus::wal_g

  $version = $zulip::common::versions['prometheus']['version']
  $dir = "/srv/zulip-prometheus-${version}"
  $bin = "${dir}/prometheus"
  $data_dir = '/var/lib/prometheus'

  zulip::external_dep { 'prometheus':
    version        => $version,
    url            => "https://github.com/prometheus/prometheus/releases/download/v${version}/prometheus-${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "prometheus-${version}.linux-${zulip::common::goarch}",
  }
  file { '/usr/local/bin/promtool':
    ensure  => link,
    target  => "${dir}/promtool",
    require => Zulip::External_Dep['prometheus'],
  }

  file { $data_dir:
    ensure  => directory,
    owner   => 'prometheus',
    group   => 'prometheus',
    require => [ User[prometheus], Group[prometheus] ],
  }
  file { '/etc/prometheus':
    ensure => directory,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
  }
  file { '/etc/prometheus/prometheus.yaml':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/prometheus/prometheus.yaml',
    notify => Service[supervisor],
  }

  file { "${zulip::common::supervisor_conf_dir}/prometheus.conf":
    ensure  => file,
    require => [
      Package[supervisor],
      Zulip::External_Dep['prometheus'],
      File[$data_dir],
      File['/etc/prometheus/prometheus.yaml'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/supervisor/conf.d/prometheus.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
