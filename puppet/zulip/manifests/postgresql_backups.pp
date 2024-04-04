# @summary Use wal-g to take daily backups of PostgreSQL
#
class zulip::postgresql_backups {
  include zulip::postgresql_common
  include zulip::wal_g

  file { '/var/log/pg_backup_and_purge.log':
    ensure => file,
    owner  => 'postgres',
    group  => 'postgres',
    mode   => '0644',
  }
  file { '/usr/local/bin/pg_backup_and_purge':
    ensure  => file,
    owner   => 'root',
    group   => 'postgres',
    mode    => '0754',
    source  => 'puppet:///modules/zulip/postgresql/pg_backup_and_purge',
    require => [
      File['/usr/local/bin/env-wal-g'],
      Package[
        $zulip::postgresql_common::postgresql,
        'python3-dateutil',
      ],
    ],
  }

  file { '/etc/cron.d/pg_backup_and_purge':
    ensure  => present,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/cron.d/pg-backup-and-purge',
    require => [
      File['/var/log/pg_backup_and_purge.log'],
      File['/usr/local/bin/pg_backup_and_purge'],
    ],
  }

  $postgresql_backup_directory = zulipconf('postgresql', 'backups_directory', '')
  if $postgresql_backup_directory != '' {
    file { $postgresql_backup_directory:
      ensure => directory,
      owner  => 'postgres',
      group  => 'postgres',
      mode   => '0600',
    }
  }

  file { "${zulip::common::nagios_plugins_dir}/zulip_postgresql_backups":
    require => Package[$zulip::common::nagios_plugins],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/nagios_plugins/zulip_postgresql_backups',
  }
}
