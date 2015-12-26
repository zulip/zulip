class zulip::memcached {
  $memcached_packages = ["memcached"]
  package { $memcached_packages: ensure => "installed" }

  file { "/etc/memcached.conf":
    require => Package[memcached],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/memcached.conf",
  }
  service { 'memcached':
    ensure     => running,
    subscribe  => File['/etc/memcached.conf'],
  }
}
