class zulip::redis {
  $redis = $::osfamily ? {
    'debian' => 'redis-server',
    'redhat' => 'redis',
  }
  $redis_packages = [ # The server itself
                      $redis,
                      ]

  package { $redis_packages: ensure => 'installed' }

  $file = '/etc/redis/redis.conf'
  $line = 'include /etc/redis/zulip-redis.conf'
  exec { 'redis':
    unless  => "/bin/grep -Fxqe '${line}' '${file}'",
    path    => '/bin',
    command => "bash -c \"(/bin/echo; /bin/echo '# Include Zulip-specific configuration'; /bin/echo '${line}') >> '${file}'\"",
    require => [Package[$redis],
                File['/etc/redis/zulip-redis.conf'],
                Exec['rediscleanup']],
  }

  exec { 'rediscleanup':
    onlyif  => 'echo "80a4cee76bac751576c3db8916fc50a6ea319428 /etc/redis/redis.conf" | sha1sum -c',
    command => 'head -n-3 /etc/redis/redis.conf | sponge /etc/redis/redis.conf',
  }

  $redis_password = zulipsecret('secrets', 'redis_password', '')
  file { '/etc/redis/zulip-redis.conf':
    ensure  => file,
    require => Package[$redis],
    owner   => 'redis',
    group   => 'redis',
    mode    => '0640',
    content => template('zulip/zulip-redis.template.erb'),
  }

  service { $redis:
    ensure    => running,
    subscribe => [File['/etc/redis/zulip-redis.conf'],
                  Exec['redis']],
  }
}
