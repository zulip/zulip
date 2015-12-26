# postgres_appdb_tuned extends postgres_appdb_base by automatically
# generating tuned database configuration.
class zulip::postgres_appdb_tuned {
  include zulip::postgres_appdb_base

  file { "/etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf.template":
    require => Package["postgresql-${zulip::base::postgres_version}"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode   => 644,
    content => template("zulip/postgresql/postgresql.conf.template.erb"),
  }

  # We can't use the built-in $memorysize fact because it's a string with human-readable units
  $total_memory = regsubst(file('/proc/meminfo'), '^.*MemTotal:\s*(\d+) kB.*$', '\1', 'M') * 1024
  $half_memory = $total_memory / 2
  $half_memory_pages = $half_memory / 4096

  file {'/etc/sysctl.d/40-postgresql.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => 644,
    content =>
"kernel.shmall = $half_memory_pages
kernel.shmmax = $half_memory

# These are the defaults on newer kernels
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
"
    }

  exec { "sysctl_p":
    command   => "/sbin/sysctl -p /etc/sysctl.d/40-postgresql.conf",
    subscribe => File['/etc/sysctl.d/40-postgresql.conf'],
    refreshonly => true,
  }

  exec { 'pgtune':
    require => Package["pgtune"],
    # Let Postgres use half the memory on the machine
    command => "pgtune -T Web -M $half_memory -i /etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf.template -o /etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf",
    refreshonly => true,
    subscribe => File["/etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf.template"]
  }

  exec { "pg_ctlcluster ${zulip::base::postgres_version} main restart":
    require => Exec["sysctl_p"],
    refreshonly => true,
    subscribe => [ Exec['pgtune'], File['/etc/sysctl.d/40-postgresql.conf'] ]
  }

}
