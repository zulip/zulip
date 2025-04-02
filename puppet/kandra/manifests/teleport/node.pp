# @summary Provide Teleport SSH access to a node.
#
# EC2 nodes will automatically join the cluster; non-EC2 hosts will
# need to set a teleport_join_token secret.  See
# https://goteleport.com/docs/agents/join-services-to-your-cluster/join-token/#generate-a-token
class kandra::teleport::node {
  include kandra::teleport::base

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
    content => template('kandra/teleport_node.yaml.template.erb'),
    order   => '01',
  }

  kandra::teleport::part { 'node': }

  $host_ca_path = '/etc/ssl/certs/teleport-ca-host.cert'
  $host_ca_extract = @("EOT")
    sqlite3 /var/lib/teleport/proc/sqlite.db "select value from kv where key = '/ids/node/current'" \
      | jq -r .spec.tls_ca_certs[] \
      | base64 -d \
      > ${host_ca_path}
    | EOT
  exec { 'teleport host CA':
    require => [Service['teleport_node'], Package['sqlite3']],
    creates => $host_ca_path,
    command => $host_ca_extract,
  }
}
