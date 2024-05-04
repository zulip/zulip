# Minimal configuration to run a Zulip application server.
# Default nginx configuration is included in extension app_frontend.pp.
class zulip::app_frontend_base {
  include zulip::nginx
  include zulip::sasl_modules
  include zulip::supervisor
  include zulip::tornado_sharding
  include zulip::hooks::base

  if $facts['os']['family'] == 'Debian' {
    # Upgrade and other tooling wants to be able to get a database
    # shell.  This is not necessary on CentOS because the PostgreSQL
    # package already includes the client.
    include zulip::postgresql_client
  }
  # For Slack import
  zulip::safepackage { 'unzip': ensure => installed }

  file { '/etc/nginx/zulip-include/app':
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/nginx/zulip-include-frontend/app',
    notify  => Service['nginx'],
  }
  file { '/etc/nginx/zulip-include/uploads.types':
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/nginx/zulip-include-frontend/uploads.types',
    notify  => Service['nginx'],
  }
  file { '/etc/nginx/zulip-include/app.d/':
    ensure => directory,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
  }

  $loadbalancers = split(zulipconf('loadbalancer', 'ips', ''), ',')
  if $loadbalancers != [] {
    file { '/etc/nginx/zulip-include/app.d/accept-loadbalancer.conf':
      require => File['/etc/nginx/zulip-include/app.d'],
      owner   => 'root',
      group   => 'root',
      mode    => '0644',
      content => template('zulip/accept-loadbalancer.conf.template.erb'),
      notify  => Service['nginx'],
    }
    file { '/etc/nginx/zulip-include/app.d/keepalive-loadbalancer.conf':
      require => File['/etc/nginx/zulip-include/app.d'],
      owner   => 'root',
      group   => 'root',
      mode    => '0644',
      source  => 'puppet:///modules/zulip/nginx/zulip-include-app.d/keepalive-loadbalancer.conf',
      notify  => Service['nginx'],
    }
  } else {
    file { ['/etc/nginx/zulip-include/app.d/accept-loadbalancer.conf',
            '/etc/nginx/zulip-include/app.d/keepalive-loadbalancer.conf']:
      ensure => absent,
      notify => Service['nginx'],
    }
  }
  file { '/etc/nginx/zulip-include/app.d/healthcheck.conf':
    require => File['/etc/nginx/zulip-include/app.d'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/nginx/healthcheck.conf.template.erb'),
    notify  => Service['nginx'],
  }

  file { '/etc/nginx/zulip-include/upstreams':
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/nginx/zulip-include-frontend/upstreams',
    notify  => Service['nginx'],
  }

  $s3_memory_cache_size = zulipconf('application_server', 's3_memory_cache_size', '1M')
  $s3_disk_cache_size = zulipconf('application_server', 's3_disk_cache_size', '200M')
  $s3_cache_inactive_time = zulipconf('application_server', 's3_cache_inactive_time', '30d')
  $configured_nginx_resolver = zulipconf('application_server', 'nameserver', '')
  if $configured_nginx_resolver == '' {
    # This may fail in the unlikely change that there is no configured
    # resolver in /etc/resolv.conf, so only call it is unset in zulip.conf
    $nginx_resolver_ip = resolver_ip()
  } elsif (':' in $configured_nginx_resolver) and ! ('.' in $configured_nginx_resolver)  and ! ('[' in $configured_nginx_resolver) {
    # Assume this is IPv6, which needs square brackets.
    $nginx_resolver_ip = "[${configured_nginx_resolver}]"
  } else {
    $nginx_resolver_ip = $configured_nginx_resolver
  }
  file { '/etc/nginx/zulip-include/s3-cache':
    require => [
      Package[$zulip::common::nginx],
      File['/srv/zulip-uploaded-files-cache'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/nginx/s3-cache.template.erb'),
    notify  => Service['nginx'],
  }

  file { '/etc/nginx/zulip-include/app.d/uploads-internal.conf':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    source  => 'puppet:///modules/zulip/nginx/zulip-include-frontend/uploads-internal.conf',
  }

  # This determines whether we run queue processors multithreaded or
  # multiprocess.  Multiprocess scales much better, but requires more
  # RAM; we just auto-detect based on available system RAM.
  #
  # Because Zulip can run in the multiprocess mode with 4GB of memory,
  # and it's a common instance size, we aim for that to be the cutoff
  # for this higher-performance mode.
  #
  # We use a cutoff less than 4000 here to detect systems advertised
  # as "4GB"; some may have as little as 4 x 1000^3 / 1024^2 ≈ 3815 MiB
  # of memory.
  $queues_multiprocess_default = $zulip::common::total_memory_mb > 3800
  $queues_multiprocess = zulipconf('application_server', 'queue_workers_multiprocess', $queues_multiprocess_default)
  $queues = [
    'deferred_work',
    'digest_emails',
    'email_mirror',
    'embed_links',
    'embedded_bots',
    'email_senders',
    'missedmessage_emails',
    'missedmessage_mobile_notifications',
    'outgoing_webhooks',
    'user_activity',
    'user_activity_interval',
    'user_presence',
  ]

  if $zulip::common::total_memory_mb > 24000 {
    $uwsgi_default_processes = 16
  } elsif $zulip::common::total_memory_mb > 12000 {
    $uwsgi_default_processes = 8
  } elsif $zulip::common::total_memory_mb > 6000 {
    $uwsgi_default_processes = 6
  } elsif $zulip::common::total_memory_mb > 3000 {
    $uwsgi_default_processes = 4
  } else {
    $uwsgi_default_processes = 3
  }
  $mobile_notification_shards = Integer(zulipconf('application_server','mobile_notification_shards', 1))
  $tornado_ports = $zulip::tornado_sharding::tornado_ports

  $proxy_host = zulipconf('http_proxy', 'host', 'localhost')
  $proxy_port = zulipconf('http_proxy', 'port', '4750')

  if ($proxy_host in ['localhost', '127.0.0.1', '::1']) and ($proxy_port == '4750') {
    include zulip::smokescreen
  }

  $katex_server = zulipconf('application_server', 'katex_server', false)
  $katex_server_port = zulipconf('application_server', 'katex_server_port', '9700')

  if $proxy_host != '' and $proxy_port != '' {
    $proxy = "http://${proxy_host}:${proxy_port}"
  } else {
    $proxy = ''
  }
  file { "${zulip::common::supervisor_conf_dir}/zulip.conf":
    ensure  => file,
    require => [Package[supervisor], Exec['stage_updated_sharding']],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/supervisor/zulip.conf.template.erb'),
    notify  => Service[$zulip::common::supervisor_service],
  }

  $uwsgi_rolling_restart = zulipconf('application_server', 'rolling_restart', false)
  $uwsgi_listen_backlog_limit = zulipconf('application_server', 'uwsgi_listen_backlog_limit', 128)
  $uwsgi_processes = zulipconf('application_server', 'uwsgi_processes', $uwsgi_default_processes)
  $somaxconn = 2 * Integer($uwsgi_listen_backlog_limit)
  file { '/etc/zulip/uwsgi.ini':
    ensure  => file,
    require => Package[supervisor],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/uwsgi.ini.template.erb'),
    notify  => Service[$zulip::common::supervisor_service],
  }
  zulip::sysctl { 'uwsgi':
    comment => 'Allow larger listen backlog',
    key     => 'net.core.somaxconn',
    value   => $somaxconn,
  }

  file { [
    '/home/zulip/tornado',
    '/home/zulip/prod-static',
    '/home/zulip/deployments',
    '/srv/zulip-locks',
    '/srv/zulip-emoji-cache',
    '/srv/zulip-uploaded-files-cache',
  ]:
    ensure => directory,
    owner  => 'zulip',
    group  => 'zulip',
    mode   => '0755',
  }
  file { [
    '/var/log/zulip/queue_error',
    '/var/log/zulip/queue_stats',
  ]:
    ensure => directory,
    owner  => 'zulip',
    group  => 'zulip',
    mode   => '0750',
  }
  $access_log_retention_days = zulipconf('application_server','access_log_retention_days', 14)
  file { '/etc/logrotate.d/zulip':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/logrotate/zulip.template.erb'),
  }

  file { "${zulip::common::nagios_plugins_dir}/zulip_app_frontend":
    require => Package[$zulip::common::nagios_plugins],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/nagios_plugins/zulip_app_frontend',
  }

  # This cron job does nothing unless RATE_LIMIT_TOR_TOGETHER is enabled.
  zulip::cron { 'fetch-tor-exit-nodes':
    minute => '17',
  }
  # This was originally added with a typo in the name.
  file { '/etc/cron.d/fetch-for-exit-nodes':
    ensure => absent,
  }
}
