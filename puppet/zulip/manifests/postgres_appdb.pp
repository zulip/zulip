class zulip::postgres_appdb {
  include zulip::postgres_common
  include zulip::supervisor

  $appdb_packages = [# Needed to run process_fts_updates
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

  # We bundle a bunch of other sysctl parameters into 40-postgresql.conf
  file { '/etc/sysctl.d/30-postgresql-shm.conf':
    ensure => absent,
  }

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
    notify => Service[supervisor],
  }

  file { '/usr/share/postgresql/9.3/tsearch_data/en_us.dict':
    ensure => 'link',
    target => '/var/cache/postgresql/dicts/en_us.dict',
  }
  file { '/usr/share/postgresql/9.3/tsearch_data/en_us.affix':
    ensure => 'link',
    target => '/var/cache/postgresql/dicts/en_us.affix',
  }
  file { "/usr/share/postgresql/9.3/tsearch_data/zulip_english.stop":
    require => Package["postgresql-9.3"],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/postgresql/zulip_english.stop",
  }

}
