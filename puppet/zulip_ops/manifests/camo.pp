class zulip_ops::camo {
  include zulip::camo

  zulip_ops::firewall_allow { 'camo': port => '9292' }

  file { '/etc/cron.d/camo':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/cron.d/camo',
  }
}
