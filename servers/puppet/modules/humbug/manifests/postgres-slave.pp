class humbug::postgres-slave {
  class { 'humbug::postgres-common': }

  file { '/etc/sysctl.d/30-postgresql-shm.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => 644,
    source   => 'puppet:///modules/humbug/postgresql/30-postgresql-shm.conf.slave',
  }

  file { "/etc/postgresql/9.1/main/postgresql.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 644,
    source => "puppet:///modules/humbug/postgresql/postgresql.conf.slave",
  }
}
