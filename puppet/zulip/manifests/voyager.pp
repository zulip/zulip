class zulip::voyager {
  include zulip::apt_repository
  include zulip::base
  include zulip::app_frontend_base
  include zulip::postgres_appdb_tuned
  include zulip::redis

  file { "/etc/nginx/sites-available/zulip-enterprise":
    require => Package["nginx-full"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/sites-available/zulip-enterprise",
    notify => Service["nginx"],
  }
  file { '/etc/nginx/sites-enabled/zulip-enterprise':
    require => Package["nginx-full"],
    ensure => 'link',
    target => '/etc/nginx/sites-available/zulip-enterprise',
    notify => Service["nginx"],
  }

  file { "/etc/cron.d/restart-zulip":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/restart-zulip",
  }
}
