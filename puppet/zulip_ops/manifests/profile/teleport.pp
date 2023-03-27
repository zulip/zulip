class zulip_ops::profile::teleport {
  include zulip_ops::profile::base

  file { '/etc/teleport_server.yaml':
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/teleport_server.yaml',
    notify => Service['teleport_server'],
  }
  zulip_ops::teleport::part { 'server': }

  # https://goteleport.com/docs/admin-guide/#ports
  # Port 443 is outward-facing, for UI
  zulip_ops::firewall_allow { 'teleport_server_ui': port => 443 }
  # Port 3023 is outward-facing, for teleport clients to connect to.
  zulip_ops::firewall_allow { 'teleport_server_proxy': port => 3023 }
  # Port 3034 is outward-facing, for teleport servers outside the
  # cluster to connect back to establish reverse proxies.
  zulip_ops::firewall_allow { 'teleport_server_reverse': port => 3024 }
  # Port 3025 is inward-facing, for other nodes to look up auth information
  zulip_ops::firewall_allow { 'teleport_server_auth': port => 3025 }
}
