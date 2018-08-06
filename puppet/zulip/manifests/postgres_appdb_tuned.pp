# postgres_appdb_tuned extends postgres_appdb_base by automatically
# generating tuned database configuration.
class zulip::postgres_appdb_tuned {
  include zulip::postgres_appdb_base

if $zulip::base::release_name == 'trusty' {
  # tools for database setup
  $postgres_appdb_tuned_packages = ['pgtune']
  package { $postgres_appdb_tuned_packages: ensure => 'installed' }

  file { "/etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf.template":
    ensure  => file,
    require => Package["postgresql-${zulip::base::postgres_version}"],
    owner   => 'postgres',
    group   => 'postgres',
    mode    => '0644',
    content => template("zulip/postgresql/${zulip::base::postgres_version}/postgresql.conf.template.erb"),
  }

  $half_memory = $zulip::base::total_memory / 2
  $half_memory_pages = $half_memory / 4096

  file {'/etc/sysctl.d/40-postgresql.conf':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content =>
"kernel.shmall = ${half_memory_pages}
kernel.shmmax = ${half_memory}

# These are the defaults on newer kernels
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
"
    }

  exec { 'sysctl_p':
    command     => '/sbin/sysctl -p /etc/sysctl.d/40-postgresql.conf',
    subscribe   => File['/etc/sysctl.d/40-postgresql.conf'],
    refreshonly => true,
  }

  exec { 'pgtune':
    require     => Package['pgtune'],
    # Let Postgres use half the memory on the machine
    # lint:ignore:140chars
    command     => "pgtune -T Web -M ${half_memory} -i /etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf.template -o /etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf",
    # lint:endignore
    refreshonly => true,
    subscribe   => File["/etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf.template"]
  }

  exec { "pg_ctlcluster ${zulip::base::postgres_version} main restart":
    require     => Exec['sysctl_p'],
    refreshonly => true,
    subscribe   => [ Exec['pgtune'], File['/etc/sysctl.d/40-postgresql.conf'] ]
  }
} else {
  $half_memory = $zulip::base::total_memory / 2
  $half_memory_pages = $half_memory / 4096

  $work_mem = $zulip::base::total_memory_mb / 512
  $shared_buffers = $zulip::base::total_memory_mb / 8
  $effective_cache_size = $zulip::base::total_memory_mb * 10 / 32
  $maintenance_work_mem = $zulip::base::total_memory_mb / 32

  $random_page_cost = zulipconf('postgresql', 'random_page_cost', undef)
  $effective_io_concurrency = zulipconf('postgresql', 'effective_io_concurrency', undef)
  $replication = zulipconf('postgresql', 'replication', undef)
  $listen_addresses = zulipconf('postgresql', 'listen_addresses', undef)

  $ssl_cert_file = zulipconf('postgresql', 'ssl_cert_file', undef)
  $ssl_key_file = zulipconf('postgresql', 'ssl_key_file', undef)
  $ssl_ca_file = zulipconf('postgresql', 'ssl_ca_file', undef)

  file { "/etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf":
    ensure  => file,
    require => Package["postgresql-${zulip::base::postgres_version}"],
    owner   => 'postgres',
    group   => 'postgres',
    mode    => '0644',
    content => template("zulip/postgresql/${zulip::base::postgres_version}/postgresql.conf.template.erb"),
  }

  exec { "pg_ctlcluster ${zulip::base::postgres_version} main restart":
    require     => Package["postgresql-${zulip::base::postgres_version}"],
    refreshonly => true,
    subscribe   => [ File["/etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf"] ]
  }
}

}
