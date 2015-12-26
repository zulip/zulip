class zulip_internal::app_frontend {
  include zulip::app_frontend_base
  include zulip::memcached
  include zulip::rabbit
  include zulip::postfix_localmail
  $app_packages = [# Needed for minify-js
                   "yui-compressor",
                   "nodejs",
                   # Needed for statsd reporting
                   "python-django-statsd-mozilla",
                   # Needed only for a disabled integration
                   "python-embedly",
                   # Needed for the ssh tunnel to the redis server
                   "autossh",
                   ]
  package { $app_packages: ensure => "installed" }

  file { "/etc/nginx/zulip-include/app.d/accept-loadbalancer.conf":
    require => Package["nginx-full"],
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip_internal/nginx/zulip-include-app.d/accept-loadbalancer.conf",
    notify => Service["nginx"],
  }

  file { '/etc/log2zulip.conf':
    ensure     => file,
    owner      => "zulip",
    group      => "zulip",
    mode       => 644,
    source     => 'puppet:///modules/zulip_internal/log2zulip.conf',
  }

  file { '/etc/cron.d/log2zulip':
    ensure     => file,
    owner      => "root",
    group      => "root",
    mode       => 644,
    source     => 'puppet:///modules/zulip_internal/cron.d/log2zulip',
  }

  file { '/etc/log2zulip.zuliprc':
    ensure     => file,
    owner      => "zulip",
    group      => "zulip",
    mode       => 600,
    source     => 'puppet:///modules/zulip_internal/log2zulip.zuliprc',
  }
  file { "/etc/cron.d/check-apns-tokens":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip_internal/cron.d/check-apns-tokens",
  }
}
