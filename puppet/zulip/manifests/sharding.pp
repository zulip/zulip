class zulip::sharding {
  include zulip::base
  include zulip::common
  include zulip::nginx

  # These two execs below are rather ugly logic to have in puppet,
  # but the advantage is that if the format of the config file generated
  # by the sharding script changes, they will automatically get re-generated
  # by puppet apply in the process of upgrading zulip, without requiring
  # the administrator to think about this step.
  exec { 'sharding_script':
    subscribe => File['/etc/zulip/zulip.conf'],
    command   => '/home/zulip/deployments/current/scripts/lib/sharding.py',
    onlyif    => 'test -f /home/zulip/deployments/current/scripts/lib/sharding.py\
  -a ! -f /home/zulip/deployments/next/scripts/lib/sharding.py',
  }
  exec { 'sharding_script_next':
    subscribe => File['/etc/zulip/zulip.conf'],
    command   => '/home/zulip/deployments/next/scripts/lib/sharding.py',
    onlyif    => 'test -f /home/zulip/deployments/next/scripts/lib/sharding.py',
  }
  # The file entries below serve only to initialize the sharding config files
  # with the correct default content for the "only one shard" setup. For this
  # reason they use "replace => false", because the files are managed by
  # the sharding script afterwards and puppet shouldn't overwrite them.
  file { '/etc/zulip/nginx_sharding.conf':
    ensure  => file,
    require => User['zulip'],
    owner   => 'zulip',
    group   => 'zulip',
    mode    => '0640',
    notify  => Service['nginx'],
    content => "set \$tornado_server http://tornado;\n",
    replace => false,
  }
  file { '/etc/zulip/sharding.json':
    ensure  => file,
    require => User['zulip'],
    owner   => 'zulip',
    group   => 'zulip',
    mode    => '0640',
    content => "{}\n",
    replace => false,
  }
}
