class zulip::redis {
  $redis_packages = [ # The server itself
                      "redis-server",
                      ]

  package { $redis_packages: ensure => "installed" }

  $file = "/etc/redis/redis.conf"
  $line = "include /etc/redis/zulip-redis.conf"
  exec { 'redis':
    unless => "/bin/grep -Fxqe '$line' '$file'",
    path => "/bin",
    command => "bash -c \"(/bin/echo; /bin/echo '# Include Zulip-specific configuration'; /bin/echo '$line') >> '$file'\"",
    require => [Package['redis-server'],
                File["/etc/redis/zulip-redis.conf"],
                Exec['rediscleanup']],
  }

  exec { 'rediscleanup':
    onlyif => "echo '80a4cee76bac751576c3db8916fc50a6ea319428 /etc/redis/redis.conf' | sha1sum -c",
    command => "head -n-3 /etc/redis/redis.conf | sponge /etc/redis/redis.conf",
  }

  $redis_password = zulipsecret("secrets", "redis_password", "")
  file { "/etc/redis/zulip-redis.conf":
    require => Package[redis-server],
    ensure => file,
    owner  => "redis",
    group  => "redis",
    mode => 640,
    content => template("zulip/zulip-redis.template.erb"),
  }

  service { 'redis-server':
    ensure     => running,
    subscribe  => [File['/etc/redis/zulip-redis.conf'],
                   Exec['redis']],
  }
}
