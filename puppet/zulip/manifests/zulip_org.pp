class zulip::zulip_org {
  include zulip::common
  include zulip::base
  include zulip::nginx

  file { '/etc/nginx/sites-available/zulip-org':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/nginx/sites-available/zulip-org',
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
