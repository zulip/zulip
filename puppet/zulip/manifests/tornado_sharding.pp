class zulip::tornado_sharding {
  include zulip::base
  include zulip::common
  include zulip::nginx

  $sharding_script = "${::zulip_scripts_path}/lib/sharding.py"
  exec { 'sharding_script':
    subscribe => File['/etc/zulip/zulip.conf'],
    command   => "bash -c '${sharding_script}'"
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
