class zulip::postgres-appdb {
  class { 'zulip::base': }
  class { 'zulip::postgres-common': }
  class { 'zulip::supervisor': }

  $appdb_packages = [ "python-psycopg2",]
  package { $appdb_packages: ensure => "installed" }

  file { "/usr/local/bin/process_fts_updates":
    ensure => file,
    owner => "root",
    group => "root",
    mode => 755,
    source => "puppet:///modules/zulip/postgresql/process_fts_updates",
  }

  file { "/etc/supervisor/conf.d/zulip_db.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/supervisord/conf.d/zulip_db.conf",
    notify => Service[supervisor],
  }

  file { "/etc/postgresql/9.1/main/pg_hba.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 640,
    source => "puppet:///modules/zulip/postgresql/pg_hba.conf",
  }

  file { "/usr/share/postgresql/9.1/tsearch_data/humbug_english.stop":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/postgresql/humbug_english.stop",
  }

}
