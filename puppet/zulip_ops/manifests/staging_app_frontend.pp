class zulip_ops::staging_app_frontend {
  include zulip_ops::base
  include zulip_ops::app_frontend

  file { "/etc/nginx/sites-available/zulip-staging":
    require => Package["nginx-full"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip_ops/nginx/sites-available/zulip-staging",
    notify => Service["nginx"],
  }
  file { '/etc/nginx/sites-enabled/zulip-staging':
    require => Package["nginx-full"],
    ensure => 'link',
    target => '/etc/nginx/sites-available/zulip-staging',
    notify => Service["nginx"],
  }
}
