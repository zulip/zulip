class zulip::tornado_sharding {
  include zulip::nginx

  # The file entries below serve only to initialize the sharding config files
  # with the correct default content for the "only one shard" setup. For this
  # reason they use "replace => false", because the files are managed by
  # the sharding script afterwards and Puppet shouldn't overwrite them.
  file { '/etc/zulip/nginx_sharding_map.conf':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    content => @(EOT),
      map "" $tornado_server {
          default http://tornado;
      }
      | EOT
    replace => false,
  }
  file { '/etc/zulip/nginx_sharding.conf':
    ensure => absent,
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

  # This creates .tmp files which scripts/refresh-sharding-and-restart
  # moves into place
  exec { 'stage_updated_sharding':
    command   => "${facts['zulip_scripts_path']}/lib/sharding.py",
    onlyif    => "${facts['zulip_scripts_path']}/lib/sharding.py --errors-ok",
    require   => [File['/etc/zulip/nginx_sharding_map.conf'], File['/etc/zulip/sharding.json']],
    logoutput => true,
    loglevel  => warning,
  }

  # The ports of Tornado processes to run on the server, computed from
  # the zulip.conf configuration. Default is just port 9800.
  $tornado_groups = zulipconf_keys('tornado_sharding').map |$key| { $key.regsubst(/_regex$/, '').split('_') }.unique
  $tornado_ports = $tornado_groups.flatten.unique

  file { '/etc/nginx/zulip-include/tornado-upstreams':
    require => [Package[$zulip::common::nginx], Exec['stage_updated_sharding']],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/nginx/tornado-upstreams.conf.template.erb'),
    notify  => Service['nginx'],
  }
}
