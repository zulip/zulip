class zulip_internal::postgres_slave {
  include zulip_internal::base
  include zulip_internal::postgres_appdb

  file { '/etc/sysctl.d/40-postgresql.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => 644,
    source   => 'puppet:///modules/zulip_internal/postgresql/40-postgresql.conf.slave',
  }

  file { "/etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf":
    require => Package["postgresql-${zulip::base::postgres_version}"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 644,
    source => "puppet:///modules/zulip_internal/postgresql/postgresql.conf.slave",
  }
}
