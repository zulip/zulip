class zulip::postgres_appdb {
  include zulip::postgres_common
  include zulip::supervisor

  $appdb_packages = [
    # Needed to run process_fts_updates
    "python-psycopg2",
    # Needed for our full text search system
    "postgresql-9.3-tsearch-extras",
  ]
  define safepackage ( $ensure = present ) {
    if !defined(Package[$title]) {
      package { $title: ensure => $ensure }
    }
  }
  safepackage { $appdb_packages: ensure => "installed" }

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
    source => "puppet:///modules/zulip/supervisor/conf.d/zulip_db.conf",
  }
}
