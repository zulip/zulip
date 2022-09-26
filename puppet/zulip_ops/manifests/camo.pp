class zulip_ops::camo {
  class { 'zulip::camo':
    listen_address => '0.0.0.0',
  }

  zulip_ops::firewall_allow { 'camo': port => '9292' }
}
