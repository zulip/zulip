class zulip_ops::postgres_common {
  include zulip::postgres_common

  $wal_g_version = '0.2.15'
  $wal_g_hash = 'ea33c2341d7bfb203c6948590c29834c013ab06a28c7a2b236a73d906f785c84'
  exec {'install-wal-g':
    command => "${::zulip_scripts_path}/setup/install-wal-g ${wal_g_version} ${wal_g_hash}",
    creates => "/usr/local/bin/wal-g-${wal_g_version}",
  }

  file { '/usr/local/bin/wal-g':
    ensure => 'link',
    target => "/usr/local/bin/wal-g-${wal_g_version}",
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
      ]
    ]
  }

  exec { 'sysctl_p':
    command     => '/sbin/sysctl -p /etc/sysctl.d/40-postgresql.conf',
    subscribe   => File['/etc/sysctl.d/40-postgresql.conf'],
    refreshonly => true,
  }


}
