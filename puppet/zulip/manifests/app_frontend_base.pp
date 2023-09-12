# Minimal configuration to run a Zulip application server.
# Default nginx configuration is included in extension app_frontend.pp.
class zulip::app_frontend_base {
  include zulip::nginx
  include zulip::sasl_modules
  include zulip::supervisor
  include zulip::tornado_sharding
  include zulip::hooks::base

  if $::os['family'] == 'Debian' {
    # Upgrade and other tooling wants to be able to get a database
    # shell.  This is not necessary on CentOS because the PostgreSQL
    # package already includes the client.  This may get us a more
    # recent client than the database server is configured to be,
    # ($zulip::postgresql_common::version), but they're compatible.
    zulip::safepackage { 'postgresql-client': ensure => installed }
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

  file { [
    # TODO/compatibility: Removed 2021-04 in Zulip 4.0; these lines can
    # be removed once one must have upgraded through Zulip 4.0 or higher
    # to get to the next release.
    '/etc/nginx/zulip-include/uploads.route',
    '/etc/nginx/zulip-include/app.d/thumbor.conf',
  ]:
    ensure => absent,
  }

  # This determines whether we run queue processors multithreaded or
  # multiprocess.  Multiprocess scales much better, but requires more
  # RAM; we just auto-detect based on available system RAM.
  $queues_multiprocess_default = $zulip::common::total_memory_mb > 3500
  $queues_multiprocess = zulipconf('application_server', 'queue_workers_multiprocess', $queues_multiprocess_default)
  $queues = [
    'deferred_work',
    'digest_emails',
    'email_mirror',
    'embed_links',
    'embedded_bots',
    'invites',
    'email_senders',
    'missedmessage_emails',
    'missedmessage_mobile_notifications',
    'outgoing_webhooks',
    'user_activity',
    'user_activity_interval',
    'user_presence',
  ]
  if $queues_multiprocess {
    $uwsgi_default_processes = 6
  } else {
    $uwsgi_default_processes = 4
  }
  $tornado_ports = $zulip::tornado_sharding::tornado_ports

  $proxy_host = zulipconf('http_proxy', 'host', 'localhost')
  $proxy_port = zulipconf('http_proxy', 'port', '4750')

  if ($proxy_host in ['localhost', '127.0.0.1', '::1']) and ($proxy_port == '4750') {
    include zulip::smokescreen
  }

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
  file { '/etc/sysctl.d/40-uwsgi.conf':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/sysctl.d/40-uwsgi.conf.erb'),
  }
  exec { 'sysctl_p_uwsgi':
    command     => '/sbin/sysctl -p /etc/sysctl.d/40-uwsgi.conf',
    subscribe   => File['/etc/sysctl.d/40-uwsgi.conf'],
    refreshonly => true,
    # We have to protect against running in Docker and other
    # containerization which prevents adjusting these.
    onlyif      => 'touch /proc/sys/net/core/somaxconn',
  }

  file { [
    '/home/zulip/tornado',
    '/home/zulip/prod-static',
    '/home/zulip/deployments',
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
  file { '/etc/cron.d/fetch-tor-exit-nodes':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/fetch-tor-exit-nodes',
  }
  # This was originally added with a typo in the name.
  file { '/etc/cron.d/fetch-for-exit-nodes':
    ensure => absent,
  }
}
