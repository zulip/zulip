# Minimal shared configuration needed to run a Zulip PostgreSQL database.
class zulip::postgresql_base {
  include zulip::postgresql_common
  include zulip::process_fts_updates

  case $facts['os']['family'] {
    'Debian': {
      $postgresql = "postgresql-${zulip::postgresql_common::version}"
      $postgresql_sharedir = "/usr/share/postgresql/${zulip::postgresql_common::version}"
      $postgresql_confdirs = [
        "/etc/postgresql/${zulip::postgresql_common::version}",
        "/etc/postgresql/${zulip::postgresql_common::version}/main",
      ]
      $postgresql_confdir = $postgresql_confdirs[-1]
      $postgresql_datadir = "/var/lib/postgresql/${zulip::postgresql_common::version}/main"
      $tsearch_datadir = "${postgresql_sharedir}/tsearch_data"
      $pgroonga_setup_sql_path = "${postgresql_sharedir}/pgroonga_setup.sql"
      $setup_system_deps = 'setup_apt_repo'
      $postgresql_restart = "pg_ctlcluster ${zulip::postgresql_common::version} main restart"
      $postgresql_dict_dict = '/var/cache/postgresql/dicts/en_us.dict'
      $postgresql_dict_affix = '/var/cache/postgresql/dicts/en_us.affix'
    }
    'RedHat': {
      $postgresql = "postgresql${zulip::postgresql_common::version}"
      $postgresql_sharedir = "/usr/pgsql-${zulip::postgresql_common::version}/share"
      $postgresql_confdirs = [
        "/var/lib/pgsql/${zulip::postgresql_common::version}",
        "/var/lib/pgsql/${zulip::postgresql_common::version}/data",
      ]
      $postgresql_confdir = $postgresql_confdirs[-1]
      $postgresql_datadir = "/var/lib/pgsql/${zulip::postgresql_common::version}/data"
      $tsearch_datadir = "${postgresql_sharedir}/tsearch_data/"
      $pgroonga_setup_sql_path = "${postgresql_sharedir}/pgroonga_setup.sql"
      $setup_system_deps = 'setup_yum_repo'
      $postgresql_restart = "systemctl restart postgresql-${zulip::postgresql_common::version}"
      # TODO Since we can't find the PostgreSQL dicts directory on CentOS yet, we
      # link directly to the hunspell directory.
      $postgresql_dict_dict = '/usr/share/myspell/en_US.dic'
      $postgresql_dict_affix = '/usr/share/myspell/en_US.aff'
    }
    default: {
      fail('osfamily not supported')
    }
  }

  file { "${tsearch_datadir}/en_us.dict":
    ensure  => link,
    require => Package[$postgresql],
    target  => $postgresql_dict_dict,
  }
  file { "${tsearch_datadir}/en_us.affix":
    ensure  => link,
    require => Package[$postgresql],
    target  => $postgresql_dict_affix,

  }
  file { "${tsearch_datadir}/zulip_english.stop":
    ensure  => file,
    require => Package[$postgresql],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/postgresql/zulip_english.stop',
  }
  file { "${zulip::common::nagios_plugins_dir}/zulip_postgresql":
    require => Package[$zulip::common::nagios_plugins],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/nagios_plugins/zulip_postgresql',
  }

  $pgroonga = zulipconf('machine', 'pgroonga', false)
  if $pgroonga {
    # Needed for optional our full text search system
    package{"${postgresql}-pgdg-pgroonga":
      ensure  => latest,
      require => [
        Package[$postgresql],
        Exec[$setup_system_deps]
      ],
    }
    exec { 'pgroonga-config':
      require => Package["${postgresql}-pgdg-pgroonga"],
      unless  => @("EOT"/$),
          test -f ${pgroonga_setup_sql_path}.applied &&
          test "$(dpkg-query --show --showformat='\${Version}' "${postgresql}-pgdg-pgroonga")" \
             = "$(cat ${pgroonga_setup_sql_path}.applied)"
          | EOT
      command => "${facts['zulip_scripts_path']}/setup/pgroonga-config ${postgresql_sharedir}",
    }
  }

  $backups_s3_bucket = zulipsecret('secrets', 's3_backups_bucket', '')
  $backups_directory = zulipconf('postgresql', 'backups_directory', '')
  if $backups_s3_bucket != '' or $backups_directory != '' {
    include zulip::postgresql_backups
  } else {
    file { '/etc/cron.d/pg_backup_and_purge':
      ensure => absent,
    }
  }
}
