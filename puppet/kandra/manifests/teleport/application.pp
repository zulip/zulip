# @summary Adds an http "application" to the Teleport configuration for the host.
#
# See https://goteleport.com/docs/application-access/
define kandra::teleport::application (
  $port,
  $description = '',
  $order = '50',
) {
  include kandra::teleport::application_top
  concat::fragment { "teleport_app_${name}":
    target  => '/etc/teleport_node.yaml',
    order   => $order,
    content => template('kandra/teleport_app.yaml.template.erb'),
  }
}
