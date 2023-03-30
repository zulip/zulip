# @summary Prometheus monitoring of postgresql servers
#
class zulip_ops::prometheus::postgresql {
  include zulip_ops::prometheus::base
  include zulip::supervisor

  $version = $zulip::common::versions['postgres_exporter']['version']
  $dir = "/srv/zulip-postgres_exporter-${version}"
  $bin = "${dir}/postgres_exporter"

  zulip::external_dep { 'postgres_exporter':
    version        => $version,
    url            => "https://github.com/prometheus-community/postgres_exporter/releases/download/v${version}/postgres_exporter-${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "postgres_exporter-${version}.linux-${zulip::common::goarch}",
  }

  exec { 'create prometheus postgres user':
    command => '/usr/bin/createuser -g pg_monitor prometheus',
    unless  => '/usr/bin/psql -tAc "select usename from pg_user" | /bin/grep -xq prometheus',
    user    => 'postgres',
  }

  zulip_ops::firewall_allow { 'postgres_exporter': port => '9187' }
  file { "${zulip::common::supervisor_conf_dir}/prometheus_postgres_exporter.conf":
    ensure  => file,
    require => [
      Exec['create prometheus postgres user'],
      User[prometheus],
      Package[supervisor],
      Zulip::External_Dep['postgres_exporter'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/supervisor/conf.d/prometheus_postgres_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
