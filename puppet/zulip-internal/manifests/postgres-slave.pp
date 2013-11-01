class zulip-internal::postgres-slave {
  include zulip-internal::base
  include zulip-internal::postgres-appdb

  # We bundle a bunch of other sysctl parameters into 40-postgresql.conf
  file { '/etc/sysctl.d/30-postgresql-shm.conf':
    ensure => absent,
  }

  file { '/etc/sysctl.d/40-postgresql.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => 644,
    source   => 'puppet:///modules/zulip-internal/postgresql/40-postgresql.conf.slave',
  }

  file { "/etc/postgresql/9.1/main/postgresql.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 644,
    source => "puppet:///modules/zulip-internal/postgresql/postgresql.conf.slave",
  }
}
