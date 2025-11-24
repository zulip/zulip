class kandra::mirror_to_czo {
  include zulip::supervisor

  # We embed the hash of the contents into the name of the process, so
  # that `supervisorctl reread` knows that it has updated.
  $full_script_hash = sha256(file('kandra/mirror_to_czo'))
  $script_hash = $full_script_hash[0,8]

  $bin = '/usr/local/bin/mirror_to_czo'
  file { $bin:
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
    source => 'puppet:///modules/kandra/mirror_to_czo',
  }

  file { "${zulip::common::supervisor_conf_dir}/mirror_to_czo.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      File[$bin],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/mirror_to_czo.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
