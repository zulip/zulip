class zulip::postgres_common {
  $postgres_packages = [# The database itself
                        "postgresql-${zulip::base::postgres_version}",
                        # tools for database monitoring
                        "ptop",
                        "python3-pip",
                        "python-pip",
                        # Needed just to support adding postgres user to 'zulip' group
                        "ssl-cert",
                        # our dictionary
                        "hunspell-en-us",
                        ]
  define safepackage ( $ensure = present ) {
    if !defined(Package[$title]) {
      package { $title: ensure => $ensure }
    }
  }
  safepackage { $postgres_packages: ensure => "installed" }

  exec {"pip3_python_deps":
    command => "/usr/bin/pip3 install 'pytz==2017.2' 'python-dateutil==2.6.1'",
    creates => "/usr/local/lib/python3.4/dist-packages/dateutil",
    require => Package['python3-pip']
  }

  exec {"pip2_python_deps":
    command => "/usr/bin/pip2 install 'pytz==2017.2' 'python-dateutil==2.6.1'",
    creates => "/usr/local/lib/python2.7/dist-packages/dateutil",
    require => Package['python-pip']
  }

  exec { "disable_logrotate":
    command => "/usr/bin/dpkg-divert --rename --divert /etc/logrotate.d/postgresql-common.disabled --add /etc/logrotate.d/postgresql-common",
    creates => '/etc/logrotate.d/postgresql-common.disabled',
  }
  file { "/usr/lib/nagios/plugins/zulip_postgres_common":
    require => Package[nagios-plugins-basic],
    recurse => true,
    purge => true,
    owner => "root",
    group => "root",
    mode => 755,
    source => "puppet:///modules/zulip/nagios_plugins/zulip_postgres_common",
  }

  file { "/usr/local/bin/env-wal-e":
    ensure => file,
    owner => "root",
    group => "postgres",
    mode => 750,
    source => "puppet:///modules/zulip/postgresql/env-wal-e",
    require => Package["postgresql-${zulip::base::postgres_version}"],
  }

  file { "/usr/local/bin/pg_backup_and_purge.py":
    ensure => file,
    owner => "root",
    group => "postgres",
    mode => 754,
    source => "puppet:///modules/zulip/postgresql/pg_backup_and_purge.py",
    require => File["/usr/local/bin/env-wal-e"],
  }

  # Use arcane puppet virtual resources to add postgres user to zulip group
  @user { 'postgres':
    groups     => ['ssl-cert'],
    membership => minimum,
    require    => [Package["postgresql-${zulip::base::postgres_version}"],
                   Package["ssl-cert"]],
  }
  User <| title == postgres |> { groups +> "zulip" }
}
