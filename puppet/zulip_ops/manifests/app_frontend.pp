class zulip_ops::app_frontend {
  include zulip::app_frontend_base
  include zulip::profile::memcached
  include zulip::profile::rabbitmq
  include zulip::postfix_localmail
  include zulip::static_asset_compiler
  include zulip::hooks::sentry
  include zulip_ops::app_frontend_monitoring

  zulip_ops::firewall_allow{ 'smtp': }
  zulip_ops::firewall_allow{ 'http': }
  zulip_ops::firewall_allow{ 'https': }

  user { 'redistunnel':
    ensure     => present,
    uid        => '1080',
    gid        => '1080',
    groups     => ['zulip'],
    shell      => '/bin/true',
    home       => '/home/redistunnel',
    managehome => true,
  }
  zulip_ops::user_dotfiles { 'redistunnel':
    keys => true,
  }
  package { 'autossh': ensure => installed }
  $redis_hostname = zulipconf('redis', 'hostname', undef)
  file { "${zulip::common::supervisor_conf_dir}/redis_tunnel.conf":
    ensure  => file,
    require => Package['supervisor', 'autossh'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/supervisor/conf.d/redis_tunnel.conf.template.erb'),
    notify  => Service['supervisor'],
  }
  # Need redis_password in its own file for Nagios
  file { '/var/lib/nagios/redis_password':
    ensure  => file,
    mode    => '0600',
    owner   => 'nagios',
    group   => 'nagios',
    content => zulipsecret('secrets', 'redis_password', ''),
  }

  # Mount /etc/zulip/well-known/ as /.well-known/
  file { '/etc/nginx/zulip-include/app.d/well-known.conf':
    require => File['/etc/nginx/zulip-include/app.d'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/nginx/zulip-include-app.d/well-known.conf',
    notify  => Service['nginx'],
  }

  # Each server does its own fetching of contributor data, since
  # we don't have a way to synchronize that among several servers.
  file { '/etc/cron.d/fetch-contributor-data':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/cron.d/fetch-contributor-data',
  }
}
