class kandra::profile::staging_app_frontend inherits kandra::profile::base {

  include kandra::app_frontend

  file { '/etc/nginx/sites-available/zulip-staging':
    ensure  => file,
    require => Package['nginx-full'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/kandra/nginx/sites-available/zulip-staging',
    notify  => Service['nginx'],
  }
  file { '/etc/nginx/sites-enabled/zulip-staging':
    ensure  => link,
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
    source => 'puppet:///modules/kandra/cron.d/check_send_receive_time',
  }
}
