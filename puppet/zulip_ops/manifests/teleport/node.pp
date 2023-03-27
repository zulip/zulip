# @summary Provide Teleport SSH access to a node.
#
# https://goteleport.com/docs/admin-guide/#adding-nodes-to-the-cluster
# details additional manual steps to allow a node to join the cluster.
class zulip_ops::teleport::node {
  include zulip_ops::teleport::base

  concat { '/etc/teleport_node.yaml':
    ensure => present,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    notify => Service['teleport_node'],
  }
  concat::fragment { 'teleport_node_base':
    target => '/etc/teleport_node.yaml',
    source => 'puppet:///modules/zulip_ops/teleport_node.yaml',
    order  => '01',
  }

  zulip_ops::teleport::part { 'node': }
}
