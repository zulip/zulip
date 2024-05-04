class kandra::app_frontend {
  include zulip::app_frontend_base
  include zulip::profile::memcached
  include zulip::profile::rabbitmq
  include zulip::postfix_localmail
  include zulip::hooks::sentry
  include kandra::app_frontend_monitoring

  kandra::firewall_allow{ 'smtp': }
  kandra::firewall_allow{ 'http': }
  kandra::firewall_allow{ 'https': }

  $redis_hostname = zulipconf('redis', 'hostname', undef)
  group { 'redistunnel':
    ensure => present,
    gid    => '1080',
  }
  user { 'redistunnel':
    ensure     => present,
    uid        => '1080',
    gid        => '1080',
    groups     => ['zulip'],
    shell      => '/bin/true',
    home       => '/home/redistunnel',
    managehome => true,
  }
  kandra::user_dotfiles { 'redistunnel':
    keys        => true,
    known_hosts => [$redis_hostname],
  }
  package { 'autossh': ensure => installed }
  file { "${zulip::common::supervisor_conf_dir}/redis_tunnel.conf":
    ensure  => file,
    require => [
      Package['supervisor', 'autossh'],
      Kandra::User_Dotfiles['redistunnel'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/redis_tunnel.conf.template.erb'),
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
    source  => 'puppet:///modules/kandra/nginx/zulip-include-app.d/well-known.conf',
    notify  => Service['nginx'],
  }

  # Each server does its own fetching of contributor data, since
  # we don't have a way to synchronize that among several servers.
  zulip::cron { 'fetch-contributor-data':
    hour    => '8',
    minute  => '0',
    command => '/home/zulip/deployments/current/tools/fetch-contributor-data',
  }
}
