# Minimal shared configuration needed to run a Zulip postgres database.
class zulip::postgres_appdb_base {
  include zulip::postgres_common
  include zulip::supervisor
  include zulip::process_fts_updates

  $appdb_packages = [
    # Needed for our full text search system
    "postgresql-${zulip::base::postgres_version}-tsearch-extras",
  ]
  zulip::safepackage { $appdb_packages: ensure => 'installed' }

  # We bundle a bunch of other sysctl parameters into 40-postgresql.conf
  file { '/etc/sysctl.d/30-postgresql-shm.conf':
    ensure => absent,
  }

  file { "/usr/share/postgresql/${zulip::base::postgres_version}/tsearch_data/en_us.dict":
    ensure  => 'link',
    require => Package["postgresql-${zulip::base::postgres_version}"],
    target  => '/var/cache/postgresql/dicts/en_us.dict',
  }
  file { "/usr/share/postgresql/${zulip::base::postgres_version}/tsearch_data/en_us.affix":
    ensure  => 'link',
    require => Package["postgresql-${zulip::base::postgres_version}"],
    target  => '/var/cache/postgresql/dicts/en_us.affix',
  }
  file { "/usr/share/postgresql/${zulip::base::postgres_version}/tsearch_data/zulip_english.stop":
    ensure  => file,
    require => Package["postgresql-${zulip::base::postgres_version}"],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/postgresql/zulip_english.stop',
  }
  file { '/usr/lib/nagios/plugins/zulip_postgres_appdb':
    require => Package[nagios-plugins-basic],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/nagios_plugins/zulip_postgres_appdb',
  }

  $pgroonga = zulipconf('machine', 'pgroonga', '')
  if $pgroonga == 'enabled' {
    apt::ppa {'ppa:groonga/ppa':
      before => Package["postgresql-${zulip::base::postgres_version}-pgroonga"],
    }

    # Needed for optional our full text search system
    package{"postgresql-${zulip::base::postgres_version}-pgroonga":
      ensure  => 'installed',
      require => Package["postgresql-${zulip::base::postgres_version}"],
    }

    $pgroonga_setup_sql_path = "/usr/share/postgresql/${zulip::base::postgres_version}/pgroonga_setup.sql"
    file { $pgroonga_setup_sql_path:
      ensure  => file,
      require => Package["postgresql-${zulip::base::postgres_version}-pgroonga"],
      owner   => 'postgres',
      group   => 'postgres',
      mode    => '0640',
      source  => 'puppet:///modules/zulip/postgresql/pgroonga_setup.sql',
    }

    exec{'create_pgroonga_extension':
      require => File[$pgroonga_setup_sql_path],
      # lint:ignore:140chars
      command => "bash -c 'cat ${pgroonga_setup_sql_path} | su postgres -c \"psql -v ON_ERROR_STOP=1 zulip\" && touch ${pgroonga_setup_sql_path}.applied'",
      # lint:endignore
      creates => "${pgroonga_setup_sql_path}.applied",
    }
  }
}
