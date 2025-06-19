class kandra::prod_app_frontend_once {
  include zulip::app_frontend_once
  include zulip::hooks::push_git_ref
  include zulip::hooks::zulip_notify
  include kandra::hooks::zulip_notify_schema_diff

  zulip::cron { 'update-first-visible-message-id':
    hour   => '7',
    minute => '0',
    manage => 'calculate_first_visible_message_id --lookback-hours 30',
  }

  zulip::cron { 'invoice-plans':
    hour   => '22',
    minute => '0',
  }
  zulip::cron { 'downgrade-small-realms-behind-on-payments':
    hour   => '17',
    minute => '0',
  }

  zulip::cron { 'check_send_receive_time':
    hour      => '*',
    minute    => '*',
    command   => '/usr/lib/nagios/plugins/zulip_app_frontend/check_send_receive_time',
    use_proxy => false,
  }
}
