# @summary Use wal-g to take daily backups of PostgreSQL
#
class zulip::postgresql_backups {
  include zulip::postgresql_common

  $wal_g_version = '1.1.1'
  $bin = "/usr/local/bin/wal-g-${wal_g_version}"
  $package = "wal-g-pg-ubuntu-20.04-${::architecture}"
  zulip::sha256_tarball_to { 'wal-g':
    url     => "https://github.com/wal-g/wal-g/releases/download/v${wal_g_version}/${package}.tar.gz",
    sha256  => '159e66a8e70254783a6a16676f1a663c795950e7e6f526726411a5111a520d1a',
    install => {
      $package => $bin,
    },
  }
  file { $bin:
    ensure  => file,
    require => Zulip::Sha256_tarball_to['wal-g'],
  }
  file { '/usr/local/bin/wal-g':
    ensure  => 'link',
    target  => $bin,
    require => File[$bin],
  }
  unless $::operatingsystem == 'Ubuntu' and $::operatingsystemrelease == '18.04' {
    # Puppet 5.5.0 and below make this always-noisy, as they spout out
    # a notify line about tidying the managed directory above.  Skip
    # on Bionic, which has that old version; they'll get tidied upon
    # upgrade to 20.04.
    tidy { '/usr/local/bin/wal-g-*':
      path    => '/usr/local/bin/',
      recurse => 1,
      rmdirs  => true,
      matches => 'wal-g-*',
      require => File[$bin],
    }
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
