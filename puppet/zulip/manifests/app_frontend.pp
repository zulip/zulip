# Default configuration for a Zulip app frontend
class zulip::app_frontend {
  include zulip::app_frontend_base
  include zulip::app_frontend_once

  file { "/etc/nginx/sites-available/zulip-enterprise":
    require => Package["nginx-full"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/sites-available/zulip-enterprise",
    notify => Service["nginx"],
  }
  file { "/etc/logrotate.d/zulip":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/logrotate/zulip",
  }
  file { '/etc/nginx/sites-enabled/zulip-enterprise':
    require => Package["nginx-full"],
    ensure => 'link',
    target => '/etc/nginx/sites-available/zulip-enterprise',
    notify => Service["nginx"],
  }

  # Trigger 2x a day certbot renew
  file { "/etc/cron.d/certbot-renew":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode   => 644,
    source => "puppet:///modules/zulip/cron.d/certbot-renew",
  }

  # Restart the server regularly to avoid potential memory leak problems.
  file { "/etc/cron.d/restart-zulip":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/restart-zulip",
  }
}
