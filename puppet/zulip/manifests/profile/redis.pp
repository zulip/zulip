class zulip::profile::redis {
  include zulip::profile::base
  case $facts['os']['family'] {
    'Debian': {
      $redis = 'redis-server'
      $redis_dir = '/etc/redis'
    }
    'RedHat': {
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

  package { $redis_packages: ensure => installed }

  $file = "${redis_dir}/redis.conf"
  $zulip_redisconf = "${redis_dir}/zulip-redis.conf"
  $line = "include ${zulip_redisconf}"
  exec { 'update-redis-conf':
    unless  => "/bin/grep -Fxqe '${line}' '${file}'",
    path    => '/bin',
    command => "bash -c \"(/bin/echo; /bin/echo '# Include Zulip-specific configuration'; /bin/echo '${line}') >> '${file}'\"",
    require => [
      Package[$redis],
      File[$zulip_redisconf],
    ],
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

  # https://redis.io/docs/management/admin/#linux
  zulip::sysctl { 'redis-server':
    key   => 'vm.overcommit_memory',
    value => '1',
  }
  package { 'sysfsutils': }
  file { '/etc/sysfs.d/40-disable-transpatent-hugepages.conf':
    require => Package['sysfsutils'],
    notify  => Service['sysfsutils'],
    content => 'kernel/mm/transparent_hugepage/enabled = never',
  }
  service { 'sysfsutils':
    ensure  => running,
    require => Package['sysfsutils'],
  }
  service { $redis:
    ensure    => running,
    require   => [
      Service['sysfsutils'],
      Package['redis-server'],
    ],
    subscribe => [
      File[$zulip_redisconf],
      Exec['update-redis-conf'],
    ],
  }
}
