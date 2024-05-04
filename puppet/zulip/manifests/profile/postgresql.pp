# @summary Extends postgresql_base by tuning the configuration.
class zulip::profile::postgresql {
  include zulip::profile::base
  include zulip::postgresql_base

  $version = $zulip::postgresql_common::version
  $work_mem = $zulip::common::total_memory_mb / 512
  $shared_buffers = $zulip::common::total_memory_mb / 8
  $effective_cache_size = $zulip::common::total_memory_mb * 10 / 32
  $maintenance_work_mem = $zulip::common::total_memory_mb / 32

  $random_page_cost = zulipconf('postgresql', 'random_page_cost', undef)
  $effective_io_concurrency = zulipconf('postgresql', 'effective_io_concurrency', undef)

  $listen_addresses = zulipconf('postgresql', 'listen_addresses', undef)

  $s3_backups_bucket = zulipsecret('secrets', 's3_backups_bucket', '')
  $replication_primary = zulipconf('postgresql', 'replication_primary', undef)
  $replication_user = zulipconf('postgresql', 'replication_user', undef)
  $replication_password = zulipsecret('secrets', 'postgresql_replication_password', '')

  $ssl_cert_file = zulipconf('postgresql', 'ssl_cert_file', undef)
  $ssl_key_file = zulipconf('postgresql', 'ssl_key_file', undef)
  $ssl_ca_file = zulipconf('postgresql', 'ssl_ca_file', undef)
  $ssl_mode = zulipconf('postgresql', 'ssl_mode', undef)

  file { $zulip::postgresql_base::postgresql_confdirs:
    ensure => directory,
    owner  => 'postgres',
    group  => 'postgres',
  }

  if $version in ['12','13','14'] {
    $postgresql_conf_file = "${zulip::postgresql_base::postgresql_confdir}/postgresql.conf"
    file { $postgresql_conf_file:
      ensure  => file,
      require => Package[$zulip::postgresql_base::postgresql],
      owner   => 'postgres',
      group   => 'postgres',
      mode    => '0644',
      content => template("zulip/postgresql/${version}/postgresql.conf.template.erb"),
    }
  } elsif $version in ['15', '16'] {
    $postgresql_conf_file = "${zulip::postgresql_base::postgresql_confdir}/conf.d/zulip.conf"
    file { $postgresql_conf_file:
      ensure  => file,
      require => Package[$zulip::postgresql_base::postgresql],
      owner   => 'postgres',
      group   => 'postgres',
      mode    => '0644',
      content => template('zulip/postgresql/zulip.conf.template.erb'),
    }
  } else {
    fail("PostgreSQL ${version} not supported")
  }

  if $replication_primary != undef and $replication_user != undef {
    # The presence of a standby.signal file triggers replication
    file { "${zulip::postgresql_base::postgresql_datadir}/standby.signal":
      ensure  => file,
      require => Package[$zulip::postgresql_base::postgresql],
      owner   => 'postgres',
      group   => 'postgres',
      mode    => '0644',
      content => '',
    }
  }

  $backups_s3_bucket = zulipsecret('secrets', 's3_backups_bucket', '')
  $backups_directory = zulipconf('postgresql', 'backups_directory', '')
  if $backups_s3_bucket != '' or $backups_directory != '' {
    $require = [File['/usr/local/bin/env-wal-g'], Package[$zulip::postgresql_base::postgresql]]
  } else {
    $require = [Package[$zulip::postgresql_base::postgresql]]
  }
  exec { $zulip::postgresql_base::postgresql_restart:
    require     => $require,
    refreshonly => true,
    subscribe   => [ File[$postgresql_conf_file] ],
    onlyif      => "test -d ${zulip::postgresql_base::postgresql_datadir}",
  }
}
