# @summary Gathers Prometheus statistics from all nodes.
#
# Only one instance is necessary.
#
class zulip_ops::profile::prometheus_server {
  include zulip_ops::profile::base
  include zulip_ops::prometheus::base

  $version = '2.27.1'
  zulip::sha256_tarball_to { 'prometheus':
    url     => "https://github.com/prometheus/prometheus/releases/download/v${version}/prometheus-${version}.linux-${::architecture}.tar.gz",
    sha256  => 'ce637d0167d5e6d2561f3bd37e1c58fe8601e13e4e1ea745653c068f6e1317ae',
    install => {
      "prometheus-${version}.linux-${::architecture}/" => "/srv/prometheus-${version}/",
    },
  }
  file { '/srv/prometheus':
    ensure  => 'link',
    target  => "/srv/prometheus-${version}/",
    require => Zulip::Sha256_tarball_to['prometheus'],
  }
  file { '/usr/local/bin/promtool':
    ensure  => 'link',
    target  => '/srv/prometheus/promtool',
    require => File['/srv/prometheus'],
  }

  file { '/var/lib/prometheus':
    ensure  => directory,
    owner   => 'prometheus',
    group   => 'prometheus',
    require => [ User[prometheus], Group[prometheus] ],
  }
  file { "${zulip::common::supervisor_conf_dir}/prometheus.conf":
    ensure  => file,
    require => [
      Package[supervisor],
      File['/srv/prometheus'],
      File['/var/lib/prometheus'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/supervisor/conf.d/prometheus.conf',
    notify  => Service[supervisor],
  }

  file { '/etc/prometheus':
    ensure => directory,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
  }
  file { '/etc/prometheus/prometheus.yaml':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/prometheus/prometheus.yaml',
    notify => Service[supervisor],
  }
}
