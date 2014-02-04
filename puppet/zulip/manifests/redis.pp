class zulip::redis {
  $redis_packages = [ # The server itself
                      "redis-server",
                      ]

  package { $redis_packages: ensure => "installed" }

  file { "/etc/redis/redis.conf":
    require => Package[redis-server],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/redis/redis.conf",
  }

  service { 'redis-server':
    ensure     => running,
    subscribe  => File['/etc/redis/redis.conf'],
  }
}
