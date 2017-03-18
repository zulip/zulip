class zulip::zulip_org {
  include zulip::base
  include zulip::nginx

  file { "/etc/nginx/sites-available/zulip-org":
    require => Package["nginx-full"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/sites-available/zulip-org",
    notify => Service["nginx"],
  }

  file { '/etc/nginx/sites-enabled/zulip-org':
    require => Package["nginx-full"],
    ensure => 'link',
    target => '/etc/nginx/sites-available/zulip-org',
    notify => Service["nginx"],
  }

  file { '/home/zulip/dist':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }
}
