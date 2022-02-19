# @summary Use wal-g to take daily backups of PostgreSQL
#
class zulip::postgresql_backups {
  include zulip::postgresql_common

  $wal_g_version = $zulip::common::versions['wal-g']['version']
  $bin = "/srv/zulip-wal-g-${wal_g_version}"
  $package = "wal-g-pg-ubuntu-20.04-${zulip::common::goarch}"

  # This tarball contains only a single file
  zulip::external_dep { 'wal-g':
    version        => $wal_g_version,
    url            => "https://github.com/wal-g/wal-g/releases/download/v${wal_g_version}/${package}.tar.gz",
    tarball_prefix => $package,
  }
  file { '/usr/local/bin/wal-g':
    ensure  => 'link',
    target  => $bin,
    require => Zulip::External_Dep['wal-g'],
  }
  # We used to install versions into /usr/local/bin/wal-g-VERSION,
  # until we moved to using Zulip::External_Dep which places them in
  # /srv/zulip-wal-g-VERSION.  Tidy old versions.
  tidy { '/usr/local/bin/wal-g-*':
    recurse => 1,
    path    => '/usr/local/bin/',
    matches => 'wal-g-*',
  }

  file { '/usr/local/bin/env-wal-g':
    ensure  => file,
    owner   => 'root',
    group   => 'postgres',
    mode    => '0750',
    source  => 'puppet:///modules/zulip/postgresql/env-wal-g',
    require => [
      Package[$zulip::postgresql_common::postgresql],
      File['/usr/local/bin/wal-g'],
    ],
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

  # Zulip 4.x and before used the `cron` resource here, which placed
  # this in the postgres user's crontab, which was not discoverable.
  # Removed 2021-11 in version 5.0; these lines can be removed when we
  # drop support for upgrading from Zulip 4 or older.
  cron { 'pg_backup_and_purge':
    ensure      => absent,
    command     => '/usr/local/bin/pg_backup_and_purge',
    environment => 'PATH=/bin:/usr/bin:/usr/local/bin',
    hour        => 2,
    minute      => 0,
    target      => 'postgres',
    user        => 'postgres',
  }
  file { '/etc/cron.d/pg_backup_and_purge':
    ensure  => present,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/cron.d/pg-backup-and-purge',
    require => File['/usr/local/bin/pg_backup_and_purge'],
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
