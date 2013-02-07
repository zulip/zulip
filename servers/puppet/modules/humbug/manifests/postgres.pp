class humbug::postgres {
  class { 'humbug::base': }

  $postgres_packages = [ "postgresql-9.1", "pgtune", ]
  package { $postgres_packages: ensure => "installed" }

  file { '/etc/sysctl.d/30-postgresql-shm.conf':
    ensure => file,
    owner  => root,
    group  => root,
    mode   => 644
  }

  file { "/etc/postgresql/9.1/main/postgresql.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 644,
    source => "/root/humbug/servers/puppet/files/postgresql/postgresql.conf",
  }

  file { "/etc/postgresql/9.1/main/pg_hba.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 640,
    source => "/root/humbug/servers/puppet/files/postgresql/pg_hba.conf",
  }

  common::append_if_no_such_line { 'shmmax':
    require    => Package['postgresql-9.1'],
    file       => '/etc/sysctl.d/30-postgresql-shm.conf',
    line       => 'kernel.shmmax = 6979321856'
  }
  common::append_if_no_such_line { 'shmall':
    require    => Package['postgresql-9.1'],
    file       => '/etc/sysctl.d/30-postgresql-shm.conf',
    line       => 'kernel.shmall = 1703936'
  }

  exec { "sysctl_p":
    command  => "sysctl -p /etc/sysctl.d/30-postgresql-shm.conf",
    require  => [ Common::Append_if_no_such_line['shmmax'],
                  Common::Append_if_no_such_line['shmall'],
                ],
  }

  exec { "disable_logrotate":
    command => "dpkg-divert --rename --divert /etc/logrotate.d/postgresql-common.disabled --add /etc/logrotate.d/postgresql-common"
  }
}
