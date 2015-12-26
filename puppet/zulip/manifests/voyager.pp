class zulip::voyager {
  include zulip::base
  include zulip::app_frontend
  include zulip::postgres_appdb_tuned
  include zulip::redis

  apt::source {'zulip':
    location    => 'http://ppa.launchpad.net/tabbott/zulip/ubuntu',
    release     => 'trusty',
    repos       => 'main',
    key         => '84C2BE60E50E336456E4749CE84240474E26AE47',
    key_source  => 'https://zulip.com/dist/keys/zulip.asc',
    pin         => '995',
    include_src => true,
  }

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

  file { '/home/zulip/prod-static':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }

  file { "/etc/cron.d/restart-zulip":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/restart-zulip",
  }
}
