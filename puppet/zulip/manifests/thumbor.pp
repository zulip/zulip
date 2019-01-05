class zulip::thumbor {
  include zulip::common
  include zulip::nginx
  include zulip::supervisor

  file { "${zulip::common::supervisor_conf_dir}/thumbor.conf":
    ensure  => file,
    require => Package[supervisor],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/supervisor/conf.d/thumbor.conf',
    notify  => Service[$zulip::common::supervisor_service],
  }

  file { '/etc/nginx/zulip-include/app.d/thumbor.conf':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    source  => 'puppet:///modules/zulip/nginx/zulip-include-app.d/thumbor.conf',
  }
}
