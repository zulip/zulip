class kandra::camo {
  class { 'zulip::camo':
    listen_address => '0.0.0.0',
  }

  kandra::firewall_allow { 'camo': port => '9292' }
}
