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
  exec { 'redis':
    unless  => "/bin/grep -Fxqe '${line}' '${file}'",
    path    => '/bin',
    command => "bash -c \"(/bin/echo; /bin/echo '# Include Zulip-specific configuration'; /bin/echo '${line}') >> '${file}'\"",
    require => [Package[$redis],
                File[$zulip_redisconf],
                Exec['rediscleanup-zuli-redis']],
  }

  # Fix the typo in the path to $zulip_redisconf introduced in
  # 071e32985c1207f20043e1cf28f82300d9f23f31 without triggering a
  # redis restart.
  $legacy_wrong_filename = "${redis_dir}/zuli-redis.conf"
  exec { 'rediscleanup-zuli-redis':
    onlyif   => "test -e ${legacy_wrong_filename}",
    command  => "
      mv ${legacy_wrong_filename} ${zulip_redisconf}
      perl -0777 -pe '
        if (m|^\\Q${line}\\E\$|m) {
          s|^\\n?(:?# Include Zulip-specific configuration\\n)?include \\Q${legacy_wrong_filename}\\E\\n||m;
        } else {
          s|^include \\Q${legacy_wrong_filename}\\E\$|${line}|m;
        }
      ' -i /etc/redis/redis.conf
    ",
    provider => shell,
  }

  $redis_password = zulipsecret('secrets', 'redis_password', '')
  file { $zulip_redisconf:
    ensure  => file,
    require => [Package[$redis], Exec['rediscleanup-zuli-redis']],
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
  file { '/run/redis':
    ensure  => directory,
    owner   => 'redis',
    group   => 'redis',
    mode    => '0755',
    require => Package[$redis],
  }
  service { $redis:
    ensure    => running,
    require   => [
      Service['sysfsutils'],
      File['/run/redis'],
    ],
    subscribe => [
      File[$zulip_redisconf],
      Exec['redis'],
    ],
  }
}
