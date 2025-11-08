# @summary Prometheus monitoring of redis servers
#
class kandra::prometheus::redis {
  include kandra::prometheus::base
  include zulip::supervisor

  $version = $zulip::common::versions['redis_exporter']['version']
  $dir = "/srv/zulip-redis_exporter-${version}"
  $bin = "${dir}/redis_exporter"

  zulip::external_dep { 'redis_exporter':
    version        => $version,
    url            => "https://github.com/oliver006/redis_exporter/releases/download/v${version}/redis_exporter-v${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "redis_exporter-v${version}.linux-${zulip::common::goarch}",
    bin            => [$bin],
    cleanup_after  => [Service[supervisor]],
  }

  kandra::firewall_allow { 'redis_exporter': port => '9121' }
  file { "${zulip::common::supervisor_conf_dir}/prometheus_redis_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      File[$bin],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/prometheus_redis_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
