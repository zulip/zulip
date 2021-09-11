class zulip_ops::profile::zulipbot_zulip_org {
  include zulip_ops::profile::base
  zulip_ops::firewall_allow { 'http': }
  zulip_ops::firewall_allow { 'https': }

  # TODO: This does not do any configuration of zulipbot itself, or of
  # caddy.
}
