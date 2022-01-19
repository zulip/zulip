# @summary Provide Teleport SSH access to a node.
#
# https://goteleport.com/docs/admin-guide/#adding-nodes-to-the-cluster
# details additional manual steps to allow a node to join the cluster.
class zulip_ops::teleport::db {
  include zulip_ops::teleport::base

  file { '/etc/teleport_db.yaml':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/teleport_db.yaml.template.erb'),
  }

  file { "${zulip::common::supervisor_conf_dir}/teleport_db.conf":
    ensure  => file,
    require => [
      Package[supervisor],
      Package[teleport],
      File['/etc/teleport_db.yaml'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/supervisor/conf.d/teleport_db.conf',
    notify  => Service[$zulip::common::supervisor_service],
  }
}
