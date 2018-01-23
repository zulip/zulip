class zulip::postgres_common {
  $postgres_packages = [# The database itself
                        "postgresql-${zulip::base::postgres_version}",
                        # tools for database monitoring
                        "ptop",
                        # Python modules used in our monitoring/worker threads
                        "python3-tz", # TODO: use a virtualenv instead
                        "python-tz", # TODO: use a virtualenv instead
                        "python3-dateutil", # TODO: use a virtualenv instead
                        "python-dateutil", # TODO: use a virtualenv instead
                        # Needed just to support adding postgres user to 'zulip' group
                        "ssl-cert",
                        # our dictionary
                        "hunspell-en-us",
                        # Postgres Nagios check plugin
                        "check-postgres",
                        ]
  define safepackage ( $ensure = present ) {
    if !defined(Package[$title]) {
      package { $title: ensure => $ensure }
    }
  }
  safepackage { $postgres_packages: ensure => "installed" }

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

  file { "/usr/local/bin/pg_backup_and_purge":
    ensure => file,
    owner => "root",
    group => "postgres",
    mode => 754,
    source => "puppet:///modules/zulip/postgresql/pg_backup_and_purge",
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
