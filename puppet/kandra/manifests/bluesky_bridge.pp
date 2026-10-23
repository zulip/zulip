class kandra::bluesky_bridge {
  include zulip::hooks::base
  include zulip::supervisor

  # We embed the hash of the contents into the name of the process, so
  # that `supervisorctl reread` knows that it has updated.
  $full_script_hash = sha256(file('kandra/bluesky_bridge'))
  $script_hash = $full_script_hash[0,8]

  $bin = '/usr/local/bin/bluesky_bridge'
  file { $bin:
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
    source => 'puppet:///modules/kandra/bluesky_bridge',
  }

  file { "${zulip::common::supervisor_conf_dir}/bluesky_bridge.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      File[$bin],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/bluesky_bridge.conf.template.erb'),
    notify  => Service[supervisor],
  }

  kandra::hooks::file { 'post-deploy.d/restart_bluesky_bridge.hook': }
}
