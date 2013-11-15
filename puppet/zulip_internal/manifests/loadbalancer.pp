class zulip_internal::loadbalancer {
  include zulip_internal::base
  include zulip::nginx
  include zulip::camo

  file { "/etc/nginx/zulip-include/":
    require => Package["nginx-full"],
    recurse => true,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip_internal/nginx/zulip-include/",
    notify => Service["nginx"],
  }

  file { "/etc/nginx/sites-available/loadbalancer":
    require => Package["nginx-full"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip_internal/nginx/sites-available/loadbalancer",
  }

  file { "/etc/motd":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip_internal/motd.lb0",
  }

  file { '/etc/nginx/sites-enabled/loadbalancer':
    ensure => 'link',
    target => '/etc/nginx/sites-available/loadbalancer',
  }

  file { "/etc/default/camo":
    require => Package[camo],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip_internal/camo_defaults",
  }
}
