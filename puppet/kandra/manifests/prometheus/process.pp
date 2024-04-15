# @summary Prometheus monitoring of Zulip server processes
#
class kandra::prometheus::process {
  include kandra::prometheus::base
  include zulip::supervisor

  $version = $zulip::common::versions['process_exporter']['version']
  $dir = "/srv/zulip-process_exporter-${version}"
  $bin = "${dir}/process-exporter"
  $conf = '/etc/zulip/process_exporter.yaml'

  zulip::external_dep { 'process_exporter':
    version        => $version,
    url            => "https://github.com/ncabatoff/process-exporter/releases/download/v${version}/process-exporter-${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "process-exporter-${version}.linux-${zulip::common::goarch}",
    bin            => [$bin],
    cleanup_after  => [Service[supervisor]],
  }

  kandra::firewall_allow { 'process_exporter': port => '9256' }
  file { $conf:
    ensure  => file,
    require => User[zulip],
    owner   => 'zulip',
    group   => 'zulip',
    mode    => '0644',
    source  => 'puppet:///modules/kandra/process_exporter.yaml',
  }
  file { "${zulip::common::supervisor_conf_dir}/prometheus_process_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      File[$bin],
      File[$conf],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/prometheus_process_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
