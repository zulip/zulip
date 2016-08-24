# Default configuration for a Zulip app frontend
class zulip::app_frontend {
  include zulip::app_frontend_base

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

  # Trigger daily digest e-mails
  file { "/etc/cron.d/send-digest-emails":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/send-digest-emails",
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
