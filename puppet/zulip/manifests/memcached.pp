class zulip::memcached {
  $memcached_packages = ["memcached"]
  package { $memcached_packages: ensure => "installed" }

  $total_memory_mb = regsubst(file('/proc/meminfo'), '^.*MemTotal:\s*(\d+) kB.*$', '\1', 'M') / 1024
  $memcached_memory = zulipconf("memcached", "memory", $total_memory_mb / 8)
  file { "/etc/memcached.conf":
    require => Package[memcached],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    content => template("zulip/memcached.conf.template.erb"),
  }
  service { 'memcached':
    ensure     => running,
    subscribe  => File['/etc/memcached.conf'],
  }
}
