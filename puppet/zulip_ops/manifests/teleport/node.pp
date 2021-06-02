# @summary Provide Teleport SSH access to a node.
#
# https://goteleport.com/docs/admin-guide/#adding-nodes-to-the-cluster
# details additional manual steps to allow a node to join the cluster.
class zulip_ops::teleport::node {
  include zulip_ops::teleport::base

  file { '/etc/teleport_node.yaml':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/teleport_node.yaml',
  }

  file { "${zulip::common::supervisor_conf_dir}/teleport_node.conf":
    ensure  => file,
    require => [
      Package[supervisor],
      Package[teleport],
      File['/etc/teleport_node.yaml'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/supervisor/conf.d/teleport_node.conf',
    notify  => Service[$zulip::common::supervisor_service],
  }

  # https://goteleport.com/docs/admin-guide/#ports
  # Port 3022 is inward-facing; the proxy uses it to set up outside
  # connections to this node.
  zulip_ops::firewall_allow { 'teleport_node': port => 3022 }
}
