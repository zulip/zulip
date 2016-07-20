class zulip_internal::postgres_common {
  include zulip::postgres_common

  $internal_postgres_packages = [# dependencies for our wal-e backup system
                                 "python-boto",
                                 "lzop",
                                 "pv",
                                 "python-pip",
                                 ]
  package { $internal_postgres_packages: ensure => "installed" }

  exec {"pip_wal-e":
    command  => "/usr/bin/pip install git+git://github.com/zbenjamin/wal-e.git#egg=wal-e",
    creates  => "/usr/local/bin/wal-e",
    require  => Package['python-pip', 'python-boto',
                        'python-gevent', 'lzop', 'pv'],
  }

  cron { "pg_backup_and_purge":
    command => "/usr/local/bin/pg_backup_and_purge.py",
    ensure => present,
    environment => "PATH=/bin:/usr/bin:/usr/local/bin",
    hour => 5,
    minute => 0,
    target => "postgres",
    user => "postgres",
    require => [ File["/usr/local/bin/pg_backup_and_purge.py"], Package["postgresql-9.1", "python-dateutil"] ]
  }

  exec { "sysctl_p":
    command   => "/sbin/sysctl -p /etc/sysctl.d/40-postgresql.conf",
    subscribe => File['/etc/sysctl.d/40-postgresql.conf'],
    refreshonly => true,
  }


}
