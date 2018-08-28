class zulip_ops::postgres_common {
  include zulip::postgres_common

  $internal_postgres_packages = [# dependencies for our wal-e backup system
    'lzop',
    'pv',
    'python3-pip',
    'python-pip',
    # "python3-gevent", # missing on trusty
    'python-gevent',
  ]
  package { $internal_postgres_packages: ensure => 'installed' }

  exec {'pip_wal-e':
    # On trusty, there is no python3-boto or python3-gevent package,
    # so we keep our `wal-e` explicitly on Python 2 for now.
    command => '/usr/bin/pip2 install git+git://github.com/zbenjamin/wal-e.git#egg=wal-e',
    creates => '/usr/local/bin/wal-e',
    require => Package['python-pip', 'python-boto', 'python-gevent',
                        'lzop', 'pv'],
  }

  cron { 'pg_backup_and_purge':
    ensure      => present,
    command     => '/usr/local/bin/pg_backup_and_purge',
    environment => 'PATH=/bin:/usr/bin:/usr/local/bin',
    hour        => 5,
    minute      => 0,
    target      => 'postgres',
    user        => 'postgres',
    require     => [
      File['/usr/local/bin/pg_backup_and_purge'],
      Package[
        "postgresql-${zulip::base::postgres_version}",
        'python3-dateutil',
        'python-dateutil'
      ]
    ]
  }

  exec { 'sysctl_p':
    command     => '/sbin/sysctl -p /etc/sysctl.d/40-postgresql.conf',
    subscribe   => File['/etc/sysctl.d/40-postgresql.conf'],
    refreshonly => true,
  }


}
