class kandra::profile::teleport inherits kandra::profile::base {


  file { '/etc/teleport_server.yaml':
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/kandra/teleport_server.yaml',
    notify => Service['teleport_server'],
  }
  kandra::teleport::part { 'server': }

  # https://goteleport.com/docs/reference/deployment/networking/#ports-with-tls-routing
  kandra::firewall_allow { 'teleport_server_ui': port => 443 }
  # Port 3025 is inward-facing, for other nodes to look up auth information
  kandra::firewall_allow { 'teleport_server_auth': port => 3025 }
}
