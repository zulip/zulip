class kandra::profile::zulipbot_zulip_org inherits kandra::profile::base {

  kandra::firewall_allow { 'http': }
  kandra::firewall_allow { 'https': }

  # TODO: This does not do any configuration of zulipbot itself, or of
  # caddy.
}
