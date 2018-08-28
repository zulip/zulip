class zulip::thumbor {
  include zulip::nginx
  include zulip::supervisor

  file { '/etc/supervisor/conf.d/thumbor.conf':
    ensure  => file,
    require => Package[supervisor],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/supervisor/conf.d/thumbor.conf',
    notify  => Service['supervisor'],
  }

  file { '/etc/nginx/zulip-include/app.d/thumbor.conf':
    ensure  => file,
    require => Package['nginx-full'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    source  => 'puppet:///modules/zulip/nginx/zulip-include-app.d/thumbor.conf',
  }
}
