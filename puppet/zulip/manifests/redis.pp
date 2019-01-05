class zulip::redis {
  case $::osfamily {
    'debian': {
      $redis = 'redis-server'
      $redis_dir = '/etc/redis'
    }
    'redhat': {
      $redis = 'redis'
      $redis_dir = '/etc'
    }
    default: {
      fail('osfamily not supported')
    }
  }
  $redis_packages = [ # The server itself
                      $redis,
                      ]

  package { $redis_packages: ensure => 'installed' }

  $file = "${redis_dir}/redis.conf"
  $zulip_redisconf = "${redis_dir}/zuli-redis.conf"
  $line = "include ${zulip_redisconf}"
  exec { 'redis':
    unless  => "/bin/grep -Fxqe '${line}' '${file}'",
    path    => '/bin',
    command => "bash -c \"(/bin/echo; /bin/echo '# Include Zulip-specific configuration'; /bin/echo '${line}') >> '${file}'\"",
    require => [Package[$redis],
                File[$zulip_redisconf],
                Exec['rediscleanup']],
  }

  exec { 'rediscleanup':
    onlyif  => "echo '80a4cee76bac751576c3db8916fc50a6ea319428 ${file}' | sha1sum -c",
    command => "head -n-3 ${file} | sponge ${file}",
  }

  $redis_password = zulipsecret('secrets', 'redis_password', '')
  file { $zulip_redisconf:
    ensure  => file,
    require => Package[$redis],
    owner   => 'redis',
    group   => 'redis',
    mode    => '0640',
    content => template('zulip/zulip-redis.template.erb'),
  }

  service { $redis:
    ensure    => running,
    subscribe => [File[$zulip_redisconf],
                  Exec['redis']],
  }
}
