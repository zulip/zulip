# @summary Prometheus monitoring of postgresql servers
#
class zulip_ops::prometheus::postgresql {
  include zulip_ops::prometheus::base
  include zulip::supervisor
  include zulip::golang

  $version = $zulip::common::versions['postgres_exporter-src']['version']
  $dir = "/srv/zulip-postgres_exporter-src-${version}"
  $bin = "/usr/local/bin/postgres_exporter-${version}-go-${zulip::golang::version}"

  # Binary builds: https://github.com/prometheus-community/postgres_exporter/releases/download/v${version}/postgres_exporter-${version}.linux-${zulip::common::goarch}.tar.gz

  zulip::external_dep { 'postgres_exporter-src':
    version        => $version,
    url            => "https://github.com/alexmv/postgres_exporter/archive/${version}.tar.gz",
    tarball_prefix => "postgres_exporter-${version}",
  }

  exec { 'compile postgres_exporter':
    command     => "make build && cp ./postgres_exporter ${bin}",
    cwd         => $dir,
    # GOCACHE is required; nothing is written to GOPATH, but it is required to be set
    environment => ['GOCACHE=/tmp/gocache', 'GOPATH=/root/go'],
    path        => [
      "${zulip::golang::dir}/bin",
      '/usr/local/bin',
      '/usr/bin',
      '/bin',
    ],
    creates     => $bin,
    require     => [
      Zulip::External_Dep['golang'],
      Zulip::External_Dep['postgres_exporter-src'],
    ]
  }
  # This resource exists purely so it doesn't get tidied; it is
  # created by the 'compile postgres_exporter' step.
  file { $bin:
    ensure  => file,
    require => Exec['compile postgres_exporter'],
  }
  tidy { '/usr/local/bin/postgres_exporter-*':
    path    => '/usr/local/bin',
    recurse => 1,
    matches => 'postgres_exporter-*',
    require => Exec['compile postgres_exporter'],
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
      File[$bin],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/supervisor/conf.d/prometheus_postgres_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
