# @summary Provide Teleport SSH access to a node.
#
# EC2 nodes will automatically join the cluster; non-EC2 hosts will
# need to set a teleport_join_token secret.  See
# https://goteleport.com/docs/agents/join-services-to-your-cluster/join-token/#generate-a-token
class zulip_ops::teleport::node {
  include zulip_ops::teleport::base

  $is_ec2 = zulipconf('machine', 'hosting_provider', 'ec2') == 'ec2'
  $join_token = zulipsecret('secrets', 'teleport_join_token', '')
  concat { '/etc/teleport_node.yaml':
    ensure => present,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    notify => Service['teleport_node'],
  }
  concat::fragment { 'teleport_node_base':
    target  => '/etc/teleport_node.yaml',
    content => template('zulip_ops/teleport_node.yaml.template.erb'),
    order   => '01',
  }

  zulip_ops::teleport::part { 'node': }
}
