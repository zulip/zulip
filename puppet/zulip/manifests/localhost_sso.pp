class zulip::localhost_sso {
  include zulip::common

  file { '/etc/nginx/zulip-include/app.d/external-sso.conf':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    source  => 'puppet:///modules/zulip/nginx/zulip-include-app.d/external-sso.conf',
  }
}
