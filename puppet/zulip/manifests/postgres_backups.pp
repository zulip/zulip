# @summary Use wal-g to take daily backups of PostgreSQL
#
class zulip::postgres_backups {
  include zulip::postgres_common

  $wal_g_version = '0.2.15'
  zulip::sha256_tarball_to { 'wal-g':
    url     => "https://github.com/wal-g/wal-g/releases/download/v${wal_g_version}/wal-g.linux-amd64.tar.gz",
    sha256  => 'ea33c2341d7bfb203c6948590c29834c013ab06a28c7a2b236a73d906f785c84',
    install => {
      'wal-g' => "/usr/local/bin/wal-g-${wal_g_version}",
    },
  }
  file { '/usr/local/bin/wal-g':
    ensure => 'link',
    target => "/usr/local/bin/wal-g-${wal_g_version}",
  }
  file { '/usr/local/bin/env-wal-g':
    ensure  => file,
    owner   => 'root',
    group   => 'postgres',
    mode    => '0750',
    source  => 'puppet:///modules/zulip/postgresql/env-wal-g',
    require => Package[$zulip::postgres_common::postgresql],
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
        $zulip::postgres_common::postgresql,
        'python3-dateutil',
      ],
    ],
  }

  cron { 'pg_backup_and_purge':
    ensure      => present,
    command     => '/usr/local/bin/pg_backup_and_purge',
    environment => 'PATH=/bin:/usr/bin:/usr/local/bin',
    hour        => 5,
    minute      => 0,
    target      => 'postgres',
    user        => 'postgres',
    require     => File['/usr/local/bin/pg_backup_and_purge'],
  }

  file { "${zulip::common::nagios_plugins_dir}/zulip_postgres_backups":
    require => Package[$zulip::common::nagios_plugins],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/nagios_plugins/zulip_postgres_backups',
  }
}
