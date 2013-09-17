class zulip::staging_app_frontend {
  class { 'zulip::base': }
  class { 'zulip::app_frontend': }

  $packages = [ "python-html2text" ]
  package { $packages: ensure => "installed" }

  file { "/etc/nginx/sites-available/zulip-staging":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/sites-available/zulip-staging",
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
    source => "puppet:///modules/zulip/cron.d/email-mirror",
  }
  file { "/etc/cron.d/clearsessions":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/clearsessions",
  }
}
