class zulip::tornado_sharding {
  include zulip::base
  include zulip::common
  include zulip::nginx

  # The file entries below serve only to initialize the sharding config files
  # with the correct default content for the "only one shard" setup. For this
  # reason they use "replace => false", because the files are managed by
  # the sharding script afterwards and puppet shouldn't overwrite them.

  # The sha256 of the empty hash, used to fingerprint the configs as
  # having been generated with a null sharding configuration.
  $empty_sha256 = sha256('')
  file { '/etc/zulip/nginx_sharding.conf':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    content => "# Configuration hash: ${empty_sha256}\nset \$tornado_server http://tornado;\n",
    replace => false,
  }
  file { '/etc/zulip/sharding.json':
    ensure  => file,
    require => User['zulip'],
    owner   => 'zulip',
    group   => 'zulip',
    mode    => '0644',
    content => "{}\n",
    replace => false,
  }

  exec { 'write_updated_sharding':
    command   => "${::zulip_scripts_path}/lib/sharding.py",
    unless    => "${::zulip_scripts_path}/lib/sharding.py --verify",
    require   => [File['/etc/zulip/nginx_sharding.conf']],
    logoutput => true,
    loglevel  => 'warning',
  }

  # The number of Tornado processes to run on the server; this
  # defaults to 1, since Tornado sharding is currently only at the
  # Realm level.
  $tornado_processes = Integer(zulipconf('application_server', 'tornado_processes', 1))
  if $tornado_processes > 1 {
    $tornado_ports = range(9800, 9800 + $tornado_processes - 1)
    $tornado_multiprocess = true
  } else {
    $tornado_multiprocess = false
  }

  file { '/etc/nginx/zulip-include/tornado-upstreams':
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/nginx/tornado-upstreams.conf.template.erb'),
    notify  => Service['nginx'],
  }
}
