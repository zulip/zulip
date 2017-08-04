# Minimal shared configuration needed to run a Zulip postgres database.
class zulip::postgres_appdb_base {
  include zulip::postgres_common
  include zulip::supervisor

  $appdb_packages = [# Needed to run process_fts_updates
                     "python3-psycopg2", # TODO: use a virtualenv instead
                     "python-psycopg2", # TODO: use a virtualenv instead
                     # Needed for our full text search system
                     "postgresql-${zulip::base::postgres_version}-tsearch-extras",
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

  file { "/usr/share/postgresql/${zulip::base::postgres_version}/tsearch_data/en_us.dict":
    require => Package["postgresql-${zulip::base::postgres_version}"],
    ensure => 'link',
    target => '/var/cache/postgresql/dicts/en_us.dict',
  }
  file { "/usr/share/postgresql/${zulip::base::postgres_version}/tsearch_data/en_us.affix":
    require => Package["postgresql-${zulip::base::postgres_version}"],
    ensure => 'link',
    target => '/var/cache/postgresql/dicts/en_us.affix',
  }
  file { "/usr/share/postgresql/${zulip::base::postgres_version}/tsearch_data/zulip_english.stop":
    require => Package["postgresql-${zulip::base::postgres_version}"],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/postgresql/zulip_english.stop",
  }
  file { "/usr/lib/nagios/plugins/zulip_postgres_appdb":
    require => Package[nagios-plugins-basic],
    recurse => true,
    purge => true,
    owner => "root",
    group => "root",
    mode => 755,
    source => "puppet:///modules/zulip/nagios_plugins/zulip_postgres_appdb",
  }

  $pgroonga = zulipconf("machine", "pgroonga", "")
  if $pgroonga == "enabled" {
    apt::ppa {'ppa:groonga/ppa':
      before => Package["postgresql-${zulip::base::postgres_version}-pgroonga"],
    }

    # Needed for optional our full text search system
    package{"postgresql-${zulip::base::postgres_version}-pgroonga":
      require => Package["postgresql-${zulip::base::postgres_version}"],
      ensure => "installed",
    }

    $pgroonga_setup_sql_path = "/usr/share/postgresql/${zulip::base::postgres_version}/pgroonga_setup.sql"
    file { $pgroonga_setup_sql_path:
      require => Package["postgresql-${zulip::base::postgres_version}-pgroonga"],
      ensure => file,
      owner  => "postgres",
      group  => "postgres",
      mode => 640,
      source => "puppet:///modules/zulip/postgresql/pgroonga_setup.sql",
    }

    exec{"create_pgroonga_extension":
      require => File["$pgroonga_setup_sql_path"],
      command  => "bash -c 'cat $pgroonga_setup_sql_path | su postgres -c \"psql -v ON_ERROR_STOP=1 zulip\" && touch $pgroonga_setup_sql_path.applied'",
      creates  => "$pgroonga_setup_sql_path.applied",
    }
  }
}
