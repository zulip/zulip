# @summary Configures a node for monitoring with Prometheus
#
class zulip_ops::prometheus::node {
  include zulip_ops::prometheus::base
  include zulip::supervisor

  $version = '1.1.2'
  zulip::sha256_tarball_to { 'node_exporter':
    url     => "https://github.com/prometheus/node_exporter/releases/download/v${version}/node_exporter-${version}.linux-${::architecture}.tar.gz",
    sha256  => '8c1f6a317457a658e0ae68ad710f6b4098db2cad10204649b51e3c043aa3e70d',
    install => {
      "node_exporter-${version}.linux-${::architecture}/node_exporter" => "/usr/local/bin/node_exporter-${version}",
    },
  }
  file { '/usr/local/bin/node_exporter':
    ensure  => 'link',
    target  => "/usr/local/bin/node_exporter-${version}",
    require => Zulip::Sha256_tarball_to['node_exporter'],
  }

  zulip_ops::firewall_allow { 'node_exporter': port => '9100' }
  file { "${zulip::common::supervisor_conf_dir}/prometheus_node_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      File['/usr/local/bin/node_exporter'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/supervisor/conf.d/prometheus_node_exporter.conf',
    notify  => Service[supervisor],
  }
}
