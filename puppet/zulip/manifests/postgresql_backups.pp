# @summary Use wal-g to take daily backups of PostgreSQL
#
class zulip::postgresql_backups {
  include zulip::postgresql_common

  $wal_g_version = '1.1'
  zulip::sha256_tarball_to { 'wal-g':
    url     => "https://github.com/wal-g/wal-g/releases/download/v${wal_g_version}/wal-g-pg-ubuntu-18.04-amd64.tar.gz",
    sha256  => '78b815bad560ee2866c91a9dfc1a1810556358e089efffe057872a4ffa5cf3bc',
    install => {
      'wal-g-pg-ubuntu-18.04-amd64' => "/usr/local/bin/wal-g-pg-${wal_g_version}",
    },
  }
  file { '/usr/local/bin/wal-g':
    ensure => 'link',
    target => "/usr/local/bin/wal-g-pg-${wal_g_version}",
  }
  file { '/usr/local/bin/env-wal-g':
    ensure  => file,
    owner   => 'root',
    group   => 'postgres',
    mode    => '0750',
    source  => 'puppet:///modules/zulip/postgresql/env-wal-g',
    require => Package[$zulip::postgresql_common::postgresql],
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

  cron { 'pg_backup_and_purge':
    ensure      => present,
    command     => '/usr/local/bin/pg_backup_and_purge',
    environment => 'PATH=/bin:/usr/bin:/usr/local/bin',
    hour        => 2,
    minute      => 0,
    target      => 'postgres',
    user        => 'postgres',
    require     => File['/usr/local/bin/pg_backup_and_purge'],
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
