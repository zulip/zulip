# @summary Provide Teleport SSH access to a node.
#
# https://goteleport.com/docs/admin-guide/#adding-nodes-to-the-cluster
# details additional manual steps to allow a node to join the cluster.
class zulip_ops::teleport::db {
  include zulip_ops::teleport::base

  $is_ec2 = zulipconf('machine', 'hosting_provider', 'ec2') == 'ec2'
  $join_token = zulipsecret('secrets', 'teleport_join_token', '')
  file { '/etc/teleport_db.yaml':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/teleport_db.yaml.template.erb'),
    notify  => Service['teleport_db'],
  }

  zulip_ops::teleport::part { 'db': }
}
