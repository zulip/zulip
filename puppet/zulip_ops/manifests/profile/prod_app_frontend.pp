class zulip_ops::profile::prod_app_frontend inherits zulip_ops::profile::base {
  include zulip_ops::app_frontend
  include zulip::hooks::zulip_notify

  Zulip_Ops::User_Dotfiles['root'] {
    keys => 'internal-limited-write-deploy-key',
  }
  Zulip_Ops::User_Dotfiles['zulip'] {
    keys => 'internal-limited-write-deploy-key',
  }

  zulip::sysctl { 'conntrack':
    comment => 'Increase conntrack kernel table size',
    key     => 'net.nf_conntrack_max',
    value   => zulipconf('application_server', 'conntrack_max', 262144),
  }

  file { '/etc/nginx/sites-available/zulip':
    ensure  => file,
    require => Package['nginx-full'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/nginx/sites-available/zulip',
    notify  => Service['nginx'],
  }

  file { '/etc/nginx/sites-enabled/zulip':
    ensure  => link,
    require => Package['nginx-full'],
    target  => '/etc/nginx/sites-available/zulip',
    notify  => Service['nginx'],
  }

  file { '/usr/lib/nagios/plugins/zulip_zephyr_mirror':
    require => Package[$zulip::common::nagios_plugins],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip_ops/nagios_plugins/zulip_zephyr_mirror',
  }

  # Prod has our Apple Push Notifications Service private key at
  # /etc/ssl/django-private/apns-dist.pem
}
