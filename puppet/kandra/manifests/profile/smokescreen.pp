class kandra::profile::smokescreen inherits kandra::profile::base {


  include zulip::profile::smokescreen
  kandra::firewall_allow { 'smokescreen': port => '4750' }
  kandra::firewall_allow { 'smokescreen_metrics': port => '9810' }

  include kandra::camo
}
