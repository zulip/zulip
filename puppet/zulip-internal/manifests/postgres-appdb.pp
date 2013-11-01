class zulip-internal::postgres-appdb {
  include zulip-internal::postgres-common
  include zulip::supervisor

  $appdb_packages = [ "python-psycopg2",]
  package { $appdb_packages: ensure => "installed" }

  file { "/usr/local/bin/process_fts_updates":
    ensure => file,
    owner => "root",
    group => "root",
    mode => 755,
    source => "puppet:///modules/zulip-internal/postgresql/process_fts_updates",
  }

  file { "/etc/supervisor/conf.d/zulip_db.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip-internal/supervisor/conf.d/zulip_db.conf",
    notify => Service[supervisor],
  }

  file { "/etc/postgresql/9.1/main/pg_hba.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 640,
    source => "puppet:///modules/zulip-internal/postgresql/pg_hba.conf",
  }

  file { "/usr/share/postgresql/9.1/tsearch_data/zulip_english.stop":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip-internal/postgresql/zulip_english.stop",
  }

}
