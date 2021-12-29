# @summary Configures a node for monitoring with Prometheus
#
class zulip_ops::prometheus::node {
  include zulip_ops::prometheus::base
  include zulip::supervisor

  $version = '1.1.2'
  $dir = "/srv/zulip-node_exporter-${version}"
  $bin = "${dir}/node_exporter"

  zulip::external_dep { 'node_exporter':
    version        => $version,
    url            => "https://github.com/prometheus/node_exporter/releases/download/v${version}/node_exporter-${version}.linux-${::architecture}.tar.gz",
    sha256         => '8c1f6a317457a658e0ae68ad710f6b4098db2cad10204649b51e3c043aa3e70d',
    tarball_prefix => "node_exporter-${version}.linux-${::architecture}",
  }

  # This was moved to an external_dep in 2021/12, and these lines can
  # be removed once all prod hosts no longer have this file.
  file { '/usr/local/bin/node_exporter':
    ensure => absent,
  }

  zulip_ops::firewall_allow { 'node_exporter': port => '9100' }
  file { "${zulip::common::supervisor_conf_dir}/prometheus_node_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      Zulip::External_Dep['node_exporter'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/supervisor/conf.d/prometheus_node_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
