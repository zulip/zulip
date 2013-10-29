class zulip-internal::staging_app_frontend {
  class { 'zulip-internal::base': }
  class { 'zulip::app_frontend': }

  $packages = [ "python-html2text" ]
  package { $packages: ensure => "installed" }

  file { "/etc/nginx/sites-available/zulip-staging":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip-internal/nginx/sites-available/zulip-staging",
  }
  file { '/etc/nginx/sites-enabled/zulip-staging':
    ensure => 'link',
    target => '/etc/nginx/sites-available/zulip-staging',
  }
  file { "/etc/cron.d/email-mirror":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip-internal/cron.d/email-mirror",
  }
  file { "/etc/cron.d/active-user-stats":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip-internal/cron.d/active-user-stats",
  }
  file { "/etc/cron.d/clearsessions":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip-internal/cron.d/clearsessions",
  }
  # Staging has our Apple Push Notifications Service private key at
  # /etc/ssl/django-private/apns-dev.pem
}
