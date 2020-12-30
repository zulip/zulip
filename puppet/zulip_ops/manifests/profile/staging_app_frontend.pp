class zulip_ops::profile::staging_app_frontend {
  include zulip_ops::profile::base
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

  # Eventually, this will go in a staging_app_frontend_once.pp
  file { '/etc/cron.d/check_send_receive_time':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/cron.d/check_send_receive_time',
  }
}
