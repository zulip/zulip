class zulip::memcached {
  $memcached_packages = ['memcached']
  package { $memcached_packages: ensure => 'installed' }

  $memcached_memory = zulipconf('memcached', 'memory', $zulip::base::total_memory_mb / 8)
  file { '/etc/memcached.conf':
    ensure  => file,
    require => Package[memcached],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/memcached.conf.template.erb'),
  }
  service { 'memcached':
    ensure    => running,
    subscribe => File['/etc/memcached.conf'],
  }
}
