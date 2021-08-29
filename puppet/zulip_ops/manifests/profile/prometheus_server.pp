# @summary Gathers Prometheus statistics from all nodes.
#
# Only one instance is necessary.
#
class zulip_ops::profile::prometheus_server {
  include zulip_ops::profile::base
  include zulip_ops::prometheus::base

  $version = '2.29.2'
  zulip::sha256_tarball_to { 'prometheus':
    url     => "https://github.com/prometheus/prometheus/releases/download/v${version}/prometheus-${version}.linux-amd64.tar.gz",
    sha256  => '51500b603a69cf1ea764b59a7456fe0c4164c4574714aca2a2b6b3d4da893348',
    install => {
      "prometheus-${version}.linux-amd64/" => "/srv/prometheus-${version}/",
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
