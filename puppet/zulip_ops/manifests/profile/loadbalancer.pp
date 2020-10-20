class zulip_ops::profile::loadbalancer {
  include zulip_ops::profile::base
  include zulip::nginx
  include zulip::camo

  file { '/etc/nginx/sites-available/loadbalancer':
    ensure  => file,
    require => Package['nginx-full'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/nginx/sites-available/loadbalancer',
    notify  => Service['nginx'],
  }

  file { '/etc/nginx/sites-enabled/loadbalancer':
    ensure  => 'link',
    require => Package['nginx-full'],
    target  => '/etc/nginx/sites-available/loadbalancer',
    notify  => Service['nginx'],
  }

  # Can be removed if you see it deployed:
  file { '/etc/cron.d/log2zulip':
    ensure => absent,
  }
}
