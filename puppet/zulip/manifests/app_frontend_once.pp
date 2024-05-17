# Cron jobs and other tools that should run on only one Zulip server
# in a cluster.

class zulip::app_frontend_once {
  include zulip::hooks::send_zulip_update_announcements

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

  # Every-hour
  zulip::cron { 'update-analytics-counts':
    minute => '5',
  }
  zulip::cron { 'check-analytics-state':
    minute => '30',
  }
  zulip::cron { 'promote-new-full-members':
    minute => '35',
  }
  zulip::cron { 'send_zulip_update_announcements':
    minute => '47',
  }

  # Daily
  zulip::cron { 'soft-deactivate-users':
    hour   => '5',
    minute => '0',
    manage => 'soft_deactivate_users -d',
  }
  zulip::cron { 'delete-old-unclaimed-attachments':
    hour   => '5',
    minute => '0',
    manage => 'delete_old_unclaimed_attachments -f',
  }
  zulip::cron { 'archive-messages':
    hour   => '6',
    minute => '0',
  }
  zulip::cron { 'send-digest-emails':
    hour   => '18',
    minute => '0',
    manage => 'enqueue_digest_emails',
  }
  zulip::cron { 'clearsessions':
    hour   => '22',
    minute => '22',
  }

}
