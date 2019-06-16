class zulip_ops::prod_app_frontend_once {
  include zulip::app_frontend_once

  file { '/etc/cron.d/update-first-visible-message-id':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/calculate-first-visible-message-id',
  }

  file { '/etc/cron.d/invoice-plans':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/invoice-plans',
  }
}
