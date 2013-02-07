class humbug::postgres {
  class { 'humbug::base': }

  $postgres_packages = [ "postgresql-9.1", "pgtune", ]
  package { $postgres_packages: ensure => "installed" }

  file { '/etc/sysctl.d/30-postgresql-shm.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => 644,
    source   => 'puppet:///modules/humbug/postgresql/30-postgresql-shm.conf',
  }

  file { "/etc/postgresql/9.1/main/postgresql.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 644,
    source => "puppet:///modules/humbug/postgresql/postgresql.conf",
  }

  file { "/etc/postgresql/9.1/main/pg_hba.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 640,
    source => "puppet:///modules/humbug/postgresql/pg_hba.conf",
  }

  exec { "sysctl_p":
    command   => "/sbin/sysctl -p /etc/sysctl.d/30-postgresql-shm.conf",
    subscribe => File['/etc/sysctl.d/30-postgresql-shm.conf'],
    refreshonly => true,
  }

  exec { "disable_logrotate":
    command => "/usr/bin/dpkg-divert --rename --divert /etc/logrotate.d/postgresql-common.disabled --add /etc/logrotate.d/postgresql-common",
    creates => '/etc/logrotate.d/postgresql-common.disabled',
  }
}
