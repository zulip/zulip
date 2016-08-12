class zulip::memcached {
  $memcached_packages = ["memcached"]
  package { $memcached_packages: ensure => "installed" }

  $memcached_memory = zulipconf("memcached", "memory", "512")
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
