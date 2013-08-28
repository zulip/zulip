class zulip::postgres-common {

  $postgres_packages = [ "postgresql-9.1", "pgtune",
                         "python-argparse", "python-gevent",
                         "lzop", "pv", "hunspell-en-us", "python-dateutil"]
  package { $postgres_packages: ensure => "installed" }

  exec {"pip_wal-e":
    command  => "/usr/bin/pip install git+git://github.com/zbenjamin/wal-e.git#egg=wal-e",
    creates  => "/usr/local/bin/wal-e",
    require  => Package['python-pip', 'python-boto', 'python-argparse',
                        'python-gevent', 'lzop', 'pv'],
  }

  file { "/usr/local/bin/env-wal-e":
    ensure => file,
    owner => "root",
    group => "postgres",
    mode => 750,
    source => "puppet:///modules/zulip/postgresql/env-wal-e",
  }

  file { "/usr/local/bin/pg_backup_and_purge.py":
    ensure => file,
    owner => "root",
    group => "postgres",
    mode => 754,
    source => "puppet:///modules/zulip/postgresql/pg_backup_and_purge.py",
    require => File["/usr/local/bin/env-wal-e"],
  }

  cron { "pg_backup_and_purge":
    command => "/usr/local/bin/pg_backup_and_purge.py",
    ensure => present,
    environment => "PATH=/bin:/usr/bin:/usr/local/bin",
    hour => 5,
    minute => 0,
    target => "postgres",
    user => "postgres",
    require => [ File["/usr/local/bin/pg_backup_and_purge.py"], Package["postgresql-9.1", "python-dateutil"] ]
  }

  exec { "disable_logrotate":
    command => "/usr/bin/dpkg-divert --rename --divert /etc/logrotate.d/postgresql-common.disabled --add /etc/logrotate.d/postgresql-common",
    creates => '/etc/logrotate.d/postgresql-common.disabled',
  }

  exec { "sysctl_p":
    command   => "/sbin/sysctl -p /etc/sysctl.d/40-postgresql.conf",
    subscribe => File['/etc/sysctl.d/40-postgresql.conf'],
    refreshonly => true,
  }


}
