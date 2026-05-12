class kandra::profile::smokescreen inherits kandra::profile::base {


  include zulip::profile::smokescreen
  kandra::firewall_allow { 'smokescreen': port => '4750' }
  kandra::teleport::prometheus_app { 'smokescreen': port => '4760' }

  include kandra::camo
}
