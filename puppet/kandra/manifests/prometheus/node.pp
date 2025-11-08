# @summary Configures a node for monitoring with Prometheus
#
class kandra::prometheus::node {
  include kandra::prometheus::base
  include zulip::supervisor

  $version = $zulip::common::versions['node_exporter']['version']
  $dir = "/srv/zulip-node_exporter-${version}"
  $bin = "${dir}/node_exporter"

  zulip::external_dep { 'node_exporter':
    version        => $version,
    url            => "https://github.com/prometheus/node_exporter/releases/download/v${version}/node_exporter-${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "node_exporter-${version}.linux-${zulip::common::goarch}",
    bin            => [$bin],
    cleanup_after  => [Service[supervisor]],
  }

  kandra::firewall_allow { 'node_exporter': port => '9100' }
  file { "${zulip::common::supervisor_conf_dir}/prometheus_node_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      File[$bin],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/prometheus_node_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
