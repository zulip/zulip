# @summary Enables application support on the node; include once.
#
# See https://goteleport.com/docs/application-access/
class kandra::teleport::application_top {
  concat::fragment { 'teleport_app':
    target => '/etc/teleport_node.yaml',
    order  => '10',
    source => 'puppet:///modules/kandra/teleport_app.yaml',
  }
}
