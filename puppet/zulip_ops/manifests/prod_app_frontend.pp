class zulip_ops::prod_app_frontend {
  include zulip_ops::base
  include zulip_ops::app_frontend
  include zulip::app_frontend_once

  file { "/etc/nginx/sites-available/zulip":
    require => Package["nginx-full"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip_ops/nginx/sites-available/zulip",
    notify => Service["nginx"],
  }

  file { '/etc/nginx/sites-enabled/zulip':
    require => Package["nginx-full"],
    ensure => 'link',
    target => '/etc/nginx/sites-available/zulip',
    notify => Service["nginx"],
  }

  file { "/usr/lib/nagios/plugins/zulip_zephyr_mirror":
    require => Package[nagios-plugins-basic],
    recurse => true,
    purge => true,
    owner => "root",
    group => "root",
    mode => 755,
    source => "puppet:///modules/zulip_ops/nagios_plugins/zulip_zephyr_mirror",
  }

  # Prod has our Apple Push Notifications Service private key at
  # /etc/ssl/django-private/apns-dist.pem
}
