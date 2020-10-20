class zulip_ops::zulip_org {
  include zulip_ops::base
  include zulip::nginx

  file { '/etc/nginx/sites-available/zulip-org':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/nginx/sites-available/zulip-org',
    notify  => Service['nginx'],
  }

  file { '/etc/nginx/sites-enabled/zulip-org':
    ensure  => 'link',
    require => Package[$zulip::common::nginx],
    target  => '/etc/nginx/sites-available/zulip-org',
    notify  => Service['nginx'],
  }

  file { '/home/zulip/dist':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }
}
