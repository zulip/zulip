# @summary Gathers Prometheus statistics from all nodes.
#
# Only one instance is necessary.
#
class kandra::profile::prometheus_server inherits kandra::profile::base {

  include kandra::prometheus::base

  # This blackbox monitoring of the backup system runs locally
  include kandra::prometheus::wal_g

  # Ditto the Akamai logs
  include kandra::prometheus::akamai

  # Export prometheus stats to status.zulip.com
  include kandra::statuspage

  $version = $zulip::common::versions['prometheus']['version']
  $dir = "/srv/zulip-prometheus-${version}"
  $bin = "${dir}/prometheus"
  $data_dir = '/var/lib/prometheus'

  zulip::external_dep { 'prometheus':
    version        => $version,
    url            => "https://github.com/prometheus/prometheus/releases/download/v${version}/prometheus-${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "prometheus-${version}.linux-${zulip::common::goarch}",
    bin            => [$bin, "${dir}/promtool"],
    cleanup_after  => [Service[supervisor]],
  }
  file { '/usr/local/bin/promtool':
    ensure  => link,
    target  => "${dir}/promtool",
    require => File["${dir}/promtool"],
    before  => Exec['Cleanup prometheus'],
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
    source => 'puppet:///modules/kandra/prometheus/prometheus.yaml',
    notify => Service[supervisor],
  }

  file { "${zulip::common::supervisor_conf_dir}/prometheus.conf":
    ensure  => file,
    require => [
      Package[supervisor],
      File[$bin],
      File[$data_dir],
      File['/etc/prometheus/prometheus.yaml'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/prometheus.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
