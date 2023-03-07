# @summary Extends postgresql_base by tuning the configuration.
class zulip::profile::postgresql {
  include zulip::profile::base
  include zulip::postgresql_base

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

  $postgresql_conf_file = "${zulip::postgresql_base::postgresql_confdir}/postgresql.conf"
  file { $postgresql_conf_file:
    ensure  => file,
    require => Package[$zulip::postgresql_base::postgresql],
    owner   => 'postgres',
    group   => 'postgres',
    mode    => '0644',
    content => template("zulip/postgresql/${zulip::postgresql_common::version}/postgresql.conf.template.erb"),
  }

  if $replication_primary != '' and $replication_user != '' {
    if $s3_backups_bucket == '' {
      $message = @(EOT/L)
          Replication is enabled, but s3_backups_bucket is not set in zulip-secrets.conf!  \
          Streaming replication requires wal-g backups be configured.
          |-EOT
      warning($message)
    }
    if $zulip::postgresql_common::version in ['11'] {
      # PostgreSQL 11 and below used a recovery.conf file for replication
      file { "${zulip::postgresql_base::postgresql_datadir}/recovery.conf":
        ensure  => file,
        require => Package[$zulip::postgresql_base::postgresql],
        owner   => 'postgres',
        group   => 'postgres',
        mode    => '0644',
        content => template('zulip/postgresql/recovery.conf.template.erb'),
      }
    } else {
      # PostgreSQL 12 and above use the presence of a standby.signal
      # file to trigger replication
      file { "${zulip::postgresql_base::postgresql_datadir}/standby.signal":
        ensure  => file,
        require => Package[$zulip::postgresql_base::postgresql],
        owner   => 'postgres',
        group   => 'postgres',
        mode    => '0644',
        content => '',
      }
    }
  }

  exec { $zulip::postgresql_base::postgresql_restart:
    require     => Package[$zulip::postgresql_base::postgresql],
    refreshonly => true,
    subscribe   => [ File[$postgresql_conf_file] ],
  }
}
