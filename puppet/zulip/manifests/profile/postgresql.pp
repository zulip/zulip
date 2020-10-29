# @summary Extends postgresql_base by tuning the configuration.
class zulip::profile::postgresql {
  include zulip::profile::base
  include zulip::postgresql_base

  case $::osfamily {
    'debian': {
      $postgresql_conf_file = "${zulip::postgresql_base::postgresql_confdir}/postgresql.conf"
      $postgres_template = "zulip/postgresql/${zulip::postgresql_common::version}/postgresql.conf.template.erb"
    }
    'redhat': {
      $postgresql_conf_file = "/var/lib/pgsql/${zulip::postgresql_common::version}/data/postgresql.conf"
      $postgres_template = "zulip/postgresql/${zulip::postgressql_common::version}/postgresql.conf.centos.template.erb"
    }
    default: {
      fail('osfamily not supported')
    }
  }

  $work_mem = $zulip::common::total_memory_mb / 512
  $shared_buffers = $zulip::common::total_memory_mb / 8
  $effective_cache_size = $zulip::common::total_memory_mb * 10 / 32
  $maintenance_work_mem = $zulip::common::total_memory_mb / 32

  $random_page_cost = zulipconf('postgresql', 'random_page_cost', undef)
  $effective_io_concurrency = zulipconf('postgresql', 'effective_io_concurrency', undef)
  $replication = zulipconf('postgresql', 'replication', undef)
  $listen_addresses = zulipconf('postgresql', 'listen_addresses', undef)

  $ssl_cert_file = zulipconf('postgresql', 'ssl_cert_file', undef)
  $ssl_key_file = zulipconf('postgresql', 'ssl_key_file', undef)
  $ssl_ca_file = zulipconf('postgresql', 'ssl_ca_file', undef)

  file { $zulip::postgresql_base::postgresql_confdirs:
    ensure => directory,
    owner  => 'postgres',
    group  => 'postgres',
  }

  # On Debian, the postgresql installer automatically initialize an
  # empty DB during install. On CentOS, we have to do it manually.
  if $::osfamily == 'redhat' {
    exec { "sudo /usr/pgsql-${zulip::postgresql_common::version}/bin/postgresql-${zulip::postgresql_common::version}-setup initdb":
      require => Package[$zulip::postgres_appdb_base::postgresql],
      creates => "$pg_datadir/pg_stat"
    }
  }

  file { $postgresql_conf_file:
    ensure  => file,
    require => Package[$zulip::postgresql_base::postgresql],
    owner   => 'postgres',
    group   => 'postgres',
    mode    => '0644',
    content => template($postgres_template),
  }

  exec { $zulip::postgresql_base::postgresql_restart:
    require     => Package[$zulip::postgresql_base::postgresql],
    refreshonly => true,
    subscribe   => [ File[$postgresql_conf_file] ],
  }
}
