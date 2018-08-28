class zulip_ops::staging_app_frontend {
  include zulip_ops::base
  include zulip_ops::app_frontend

  file { '/etc/nginx/sites-available/zulip-staging':
    ensure  => file,
    require => Package['nginx-full'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/nginx/sites-available/zulip-staging',
    notify  => Service['nginx'],
  }
  file { '/etc/nginx/sites-enabled/zulip-staging':
    ensure  => 'link',
    require => Package['nginx-full'],
    target  => '/etc/nginx/sites-available/zulip-staging',
    notify  => Service['nginx'],
  }
}
