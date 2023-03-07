# @summary Prometheus monitoring of tornado processes
#
class zulip_ops::prometheus::tornado {
  $version = $zulip::common::versions['process_exporter']['version']
  $dir = "/srv/zulip-process_exporter-${version}"
  $bin = "${dir}/process-exporter"
  $conf = '/etc/zulip/tornado_process_exporter.yaml'

  zulip::external_dep { 'process_exporter':
    version        => $version,
    url            => "https://github.com/ncabatoff/process-exporter/releases/download/v${version}/process-exporter-${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "process-exporter-${version}.linux-${zulip::common::goarch}",
  }

  zulip_ops::firewall_allow { 'tornado_exporter': port => '9256' }
  file { $conf:
    ensure  => file,
    require => User[zulip],
    owner   => 'zulip',
    group   => 'zulip',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/tornado_process_exporter.yaml',
  }
  file { "${zulip::common::supervisor_conf_dir}/prometheus_tornado_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      Zulip::External_Dep['process_exporter'],
      File[$conf],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/supervisor/conf.d/prometheus_tornado_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
