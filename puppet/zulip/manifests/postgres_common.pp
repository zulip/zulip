class zulip::postgres_common {
  case $::osfamily {
    'debian': {
      $nagios_plugins = 'nagios-plugins-basic'
      $postgresql = "postgresql-${zulip::base::postgres_version}"
      $postgres_packages = [
        # The database itself
        $postgresql,
        # tools for database monitoring
        'ptop',
        # Needed just to support adding postgres user to 'zulip' group
        'ssl-cert',
        # our dictionary
        'hunspell-en-us',
        # Postgres Nagios check plugin
        'check-postgres',
        # Python modules used in our monitoring/worker threads
        'python3-tz', # TODO: use a virtualenv instead
        'python-tz', # TODO: use a virtualenv instead
        'python3-dateutil', # TODO: use a virtualenv instead
        'python-dateutil', # TODO: use a virtualenv instead
      ]
    }
    'redhat': {
      $nagios_plugins = 'nagios-plugins'
      $postgresql = "postgresql${zulip::base::postgres_version}"
      $postgres_packages = [
        $postgresql,
        "${postgresql}-server",
        "${postgresql}-devel",
        'pg_top',
        'ssl-cert',  #?? TODO no equivalent on CentOS 7
        'hunspell-en-US',
        # exists on CentOS 6 and Fedora 29 but not CentOS 7
        # see https://pkgs.org/download/check_postgres
        # alternatively, download directly from:
        # https://bucardo.org/check_postgres/
        # 'check-postgres',  # TODO
      ]
      exec {'pip2_deps':
        # Python modules used in our monitoring/worker threads
        command => '/usr/bin/pip2 install pytz python-dateutil'
      }
      exec {'pip3_deps':
        command => 'python3 -m pip install pytz python-dateutil'
      }
    }
    default: {
      fail('osfamily not supported')
    }
  }

  zulip::safepackage { $postgres_packages: ensure => 'installed' }

  if $::osfamily == 'debian' {
    # The logrotate file only created in debian-based systems
    exec { 'disable_logrotate':
      # lint:ignore:140chars
      command => '/usr/bin/dpkg-divert --rename --divert /etc/logrotate.d/postgresql-common.disabled --add /etc/logrotate.d/postgresql-common',
      # lint:endignore
      creates => '/etc/logrotate.d/postgresql-common.disabled',
    }
  }
  file { '/usr/lib/nagios/plugins/zulip_postgres_common':
    require => Package[$nagios_plugins],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/nagios_plugins/zulip_postgres_common',
  }

  file { '/usr/local/bin/env-wal-e':
    ensure  => file,
    owner   => 'root',
    group   => 'postgres',
    mode    => '0750',
    source  => 'puppet:///modules/zulip/postgresql/env-wal-e',
    require => Package[$postgresql],
  }

  file { '/usr/local/bin/pg_backup_and_purge':
    ensure  => file,
    owner   => 'root',
    group   => 'postgres',
    mode    => '0754',
    source  => 'puppet:///modules/zulip/postgresql/pg_backup_and_purge',
    require => File['/usr/local/bin/env-wal-e'],
  }

  # Use arcane puppet virtual resources to add postgres user to zulip group
  @user { 'postgres':
    groups     => ['ssl-cert'],
    membership => minimum,
    require    => [
      Package[$postgresql],
      Package['ssl-cert']
    ],
  }
  User <| title == postgres |> { groups +> 'zulip' }
}
