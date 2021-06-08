class zulip_ops::profile::chat_zulip_org {
  include zulip::profile::standalone
  include zulip::profile::smokescreen
  include zulip::postfix_localmail
  include zulip::postgresql_backups

  include zulip_ops::profile::base
  zulip_ops::firewall_allow { 'http': }
  zulip_ops::firewall_allow { 'https': }
  zulip_ops::firewall_allow { 'smtp': }
}
