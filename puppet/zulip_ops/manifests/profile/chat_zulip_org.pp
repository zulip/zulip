class zulip_ops::profile::chat_zulip_org {
  include zulip::profile::standalone
  include zulip::postfix_localmail

  include zulip_ops::profile::base
  include zulip_ops::app_frontend_monitoring
  include zulip_ops::prometheus::redis
  zulip_ops::firewall_allow { 'http': }
  zulip_ops::firewall_allow { 'https': }
  zulip_ops::firewall_allow { 'smtp': }

  file { '/etc/cron.d/check_send_receive_time':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/cron.d/check_send_receive_time',
  }
}
