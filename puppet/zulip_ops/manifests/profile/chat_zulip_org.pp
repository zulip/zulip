class zulip_ops::profile::chat_zulip_org {
  import zulip::profile::standalone
  import zulip::profile::smokescreen
  import zulip::postfix_localmail
  import zulip::postgresql_backups

  import zulip_ops::profile::base
  zulip_ops::firewall_allow { 'http': }
  zulip_ops::firewall_allow { 'https': }
  zulip_ops::firewall_allow { 'smtp': }
}
