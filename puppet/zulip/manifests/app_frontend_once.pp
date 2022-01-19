# Cron jobs and other tools that should run on only one Zulip server
# in a cluster.

class zulip::app_frontend_once {
  $proxy_host = zulipconf('http_proxy', 'host', 'localhost')
  $proxy_port = zulipconf('http_proxy', 'port', '4750')
  if $proxy_host != '' and $proxy_port != '' {
    $proxy = "http://${proxy_host}:${proxy_port}"
  } else {
    $proxy = ''
  }
  file { "${zulip::common::supervisor_conf_dir}/zulip-once.conf":
    ensure  => file,
    require => [Package[supervisor], Exec['stage_updated_sharding']],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/supervisor/zulip-once.conf.template.erb'),
    notify  => Service[$zulip::common::supervisor_service],
  }

  file { '/etc/cron.d/send-digest-emails':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/send-digest-emails',
  }

  file { '/etc/cron.d/update-analytics-counts':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/update-analytics-counts',
  }

  file { '/etc/cron.d/check-analytics-state':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/check-analytics-state',
  }

  file { '/etc/cron.d/soft-deactivate-users':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/soft-deactivate-users',
  }

  file { '/etc/cron.d/archive-messages':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/archive-messages',
  }

  file { '/etc/cron.d/clearsessions':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/clearsessions',
  }
}
