class kandra::camo {
  class { 'zulip::camo':
    listen_address => '0.0.0.0',
  }

  kandra::teleport::prometheus_app { 'camo': port => '9292' }
}
