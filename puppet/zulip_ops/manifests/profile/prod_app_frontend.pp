class zulip_ops::profile::prod_app_frontend inherits zulip_ops::profile::base {
  include zulip_ops::app_frontend
  include zulip::hooks::zulip_notify

  $conntrack_max = zulipconf('application_server', 'conntrack_max', 262144)
  zulip::sysctl { 'conntrack':
    content => template('zulip_ops/sysctl.d/40-conntrack.conf.erb'),
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
