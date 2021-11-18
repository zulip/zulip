class zulip_ops::camo {
  include zulip::camo

  zulip_ops::firewall_allow { 'camo': port => '9292' }
}
