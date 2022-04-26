# @summary Enables application support on the node; include once.
#
# See https://goteleport.com/docs/application-access/
class zulip_ops::teleport::application_top {
  concat::fragment { 'teleport_app':
    target => '/etc/teleport_node.yaml',
    order  => '10',
    source => 'puppet:///modules/zulip_ops/teleport_app.yaml',
  }
}
