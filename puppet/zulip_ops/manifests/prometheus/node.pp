# @summary Configures a node for monitoring with Prometheus
#
class zulip_ops::prometheus::node {
  include zulip_ops::prometheus::base
  include zulip::supervisor

  $version = $zulip::common::versions['node_exporter']['version']
  $dir = "/srv/zulip-node_exporter-${version}"
  $bin = "${dir}/node_exporter"

  zulip::external_dep { 'node_exporter':
    version        => $version,
    url            => "https://github.com/prometheus/node_exporter/releases/download/v${version}/node_exporter-${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "node_exporter-${version}.linux-${zulip::common::goarch}",
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
