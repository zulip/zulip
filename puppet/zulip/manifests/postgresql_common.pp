class zulip::postgresql_common {
  include zulip::snakeoil
  $version = zulipconf('postgresql', 'version', undef)
  case $::os['family'] {
    'Debian': {
      $postgresql = "postgresql-${version}"
      $postgresql_packages = [
        # The database itself
        $postgresql,
        # tools for database monitoring; formerly ptop
        'pgtop',
        # our dictionary
        'hunspell-en-us',
        # PostgreSQL Nagios check plugin
        'check-postgres',
        # Python modules used in our monitoring/worker threads
        'python3-dateutil', # TODO: use a virtualenv instead
      ]
      $postgresql_user_reqs = [
        Package[$postgresql],
        Package['ssl-cert'],
      ]
    }
    'RedHat': {
      $postgresql = "postgresql${version}"
      $postgresql_packages = [
        $postgresql,
        "${postgresql}-server",
        "${postgresql}-devel",
        'pg_top',
        'hunspell-en-US',
        # exists on CentOS 6 and Fedora 29 but not CentOS 7
        # see https://pkgs.org/download/check_postgres
        # alternatively, download directly from:
        # https://bucardo.org/check_postgres/
        # 'check-postgres',  # TODO
      ]
      exec {'pip3_deps':
        command => 'python3 -m pip install python-dateutil',
      }
      group { 'ssl-cert':
        ensure => present,
      }
      # allows ssl-cert group to read /etc/pki/tls/private
      file { '/etc/pki/tls/private':
        ensure => directory,
        mode   => '0750',
        owner  => 'root',
        group  => 'ssl-cert',
      }
      $postgresql_user_reqs = [
        Package[$postgresql],
        Group['ssl-cert'],
      ]
    }
    default: {
      fail('osfamily not supported')
    }
  }

  zulip::safepackage { $postgresql_packages:
    ensure  => installed,
    require => Exec['generate-default-snakeoil'],
  }

  if $::os['family'] == 'Debian' {
    # The logrotate file only created in debian-based systems
    exec { 'disable_logrotate':
      # lint:ignore:140chars
      command => '/usr/bin/dpkg-divert --rename --divert /etc/logrotate.d/postgresql-common.disabled --add /etc/logrotate.d/postgresql-common',
      # lint:endignore
      creates => '/etc/logrotate.d/postgresql-common.disabled',
    }
  }

  # Use arcane puppet virtual resources to add postgres user to zulip group
  @user { 'postgres':
    groups     => ['ssl-cert'],
    membership => minimum,
    require    => $postgresql_user_reqs,
  }
  User <| title == postgres |> { groups +> 'zulip' }
}
