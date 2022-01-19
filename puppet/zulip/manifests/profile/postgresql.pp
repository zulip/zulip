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

  $replication = zulipconf('postgresql', 'replication', undef)
  $replication_primary = zulipconf('postgresql', 'replication_primary', undef)
  $replication_user = zulipconf('postgresql', 'replication_user', undef)

  $ssl_cert_file = zulipconf('postgresql', 'ssl_cert_file', undef)
  $ssl_key_file = zulipconf('postgresql', 'ssl_key_file', undef)
  $ssl_ca_file = zulipconf('postgresql', 'ssl_ca_file', undef)

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
    if $zulip::postgresql_common::version in ['10', '11'] {
      # PostgreSQL 11 and below used a recovery.conf file for replication
      file { "${zulip::postgresql_base::postgresql_confdir}/recovery.conf":
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
      file { "${zulip::postgresql_base::postgresql_confdir}/standby.signal":
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
