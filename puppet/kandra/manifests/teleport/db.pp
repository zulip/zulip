# @summary Provide Teleport SSH access to a node.
#
# https://goteleport.com/docs/admin-guide/#adding-nodes-to-the-cluster
# details additional manual steps to allow a node to join the cluster.
class kandra::teleport::db {
  include kandra::teleport::base

  $fqdn = $facts['networking']['fqdn']
  $is_ec2 = zulipconf('machine', 'hosting_provider', 'ec2') == 'ec2'
  $join_token = zulipsecret('secrets', 'teleport_join_token', '')
  file { '/etc/teleport_db.yaml':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/teleport_db.yaml.template.erb'),
    notify  => Service['teleport_db'],
  }

  kandra::teleport::part { 'db': }
}
