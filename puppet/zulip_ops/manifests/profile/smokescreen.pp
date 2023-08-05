class zulip_ops::profile::smokescreen {
  include zulip_ops::profile::base

  include zulip::profile::smokescreen
  zulip_ops::firewall_allow { 'smokescreen': port => '4750' }
  zulip_ops::firewall_allow { 'smokescreen_metrics': port => '9810' }

  include zulip_ops::camo
}
