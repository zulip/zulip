# @summary Prometheus monitoring of postgresql servers
#
class kandra::prometheus::postgresql {
  include kandra::prometheus::base
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
    ],
    notify      => Exec['Cleanup postgres_exporter'],
  }
  # This resource is created by the 'compile postgres_exporter' step.
  file { $bin:
    ensure  => file,
    require => Exec['compile postgres_exporter'],
  }
  exec { 'Cleanup postgres_exporter':
    refreshonly => true,
    provider    => shell,
    onlyif      => "ls /usr/local/bin/postgres_exporter-* | grep -xv '${bin}'",
    command     => "ls /usr/local/bin/postgres_exporter-* | grep -xv '${bin}' | xargs rm -r",
    require     => [File[$bin], Service[supervisor]],
  }

  if false {
    # This is left commented out, since it only makes sense to run
    # against a server where the database exists and is writable --
    # the former of which happens outside th scope of puppet right
    # now, and the latter of which can only be determined after the
    # database is in place.  Given that it has been run once, we do
    # not expect to ever need it to run again; it is left here for
    # completeness.
    include zulip::postgresql_client
    exec { 'create prometheus postgres user':
      require => Class['zulip::postgresql_client'],
      command => '/usr/bin/createuser -g pg_monitor prometheus',
      unless  => 'test -f /usr/bin/psql && /usr/bin/psql -tAc "select usename from pg_user" | /bin/grep -xq prometheus)',
      user    => 'postgres',
      before  => File["${zulip::common::supervisor_conf_dir}/prometheus_postgres_exporter.conf"],
    }
  }

  kandra::firewall_allow { 'postgres_exporter': port => '9187' }
  file { "${zulip::common::supervisor_conf_dir}/prometheus_postgres_exporter.conf":
    ensure  => file,
    require => [
      User[prometheus],
      Package[supervisor],
      File[$bin],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/prometheus_postgres_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
