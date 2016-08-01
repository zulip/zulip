class zulip_ops::app_frontend {
  include zulip::app_frontend_base
  include zulip::memcached
  include zulip::rabbit
  include zulip::postfix_localmail
  include zulip::static_asset_compiler
  $app_packages = [# Needed for the ssh tunnel to the redis server
                   "autossh",
                   ]
  package { $app_packages: ensure => "installed" }
  $hosts_domain = zulipconf("nagios", "hosts_domain", undef)

  file { "/etc/logrotate.d/zulip":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/logrotate/zulip",
  }

  file { '/etc/log2zulip.conf':
    ensure     => file,
    owner      => "zulip",
    group      => "zulip",
    mode       => 644,
    source     => 'puppet:///modules/zulip_ops/log2zulip.conf',
  }

  file { '/etc/cron.d/log2zulip':
    ensure     => file,
    owner      => "root",
    group      => "root",
    mode       => 644,
    source     => 'puppet:///modules/zulip_ops/cron.d/log2zulip',
  }

  file { '/etc/cron.d/check_send_receive_time':
    ensure     => file,
    owner      => "root",
    group      => "root",
    mode       => 644,
    source     => 'puppet:///modules/zulip_ops/cron.d/check_send_receive_time',
  }

  file { '/etc/log2zulip.zuliprc':
    ensure     => file,
    owner      => "zulip",
    group      => "zulip",
    mode       => 600,
    source     => 'puppet:///modules/zulip_ops/log2zulip.zuliprc',
  }
  file { "/etc/cron.d/check-apns-tokens":
    ensure => absent,
  }

  file { "/etc/supervisor/conf.d/redis_tunnel.conf":
    require => Package["supervisor", "autossh"],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    content => template("zulip_ops/supervisor/conf.d/redis_tunnel.conf.template.erb"),
    notify => Service["supervisor"],
  }
  # Need redis_password in its own file for Nagios
  file { '/var/lib/nagios/redis_password':
    ensure     => file,
    mode       => 600,
    owner      => "nagios",
    group      => "nagios",
    content    => zulipsecret('secrets', 'redis_password', ''),
  }

}
