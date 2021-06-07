# @summary Adds an http "application" to the Teleport configuration for the host.
#
# See https://goteleport.com/docs/application-access/
define zulip_ops::teleport::application (
  $port,
  $order = '50',
) {
  concat::fragment { "teleport_app_${name}":
    target  => '/etc/teleport_node.yaml',
    order   => $order,
    content => "    - name: ${name}\n      uri: http://127.0.0.1:${port}\n",
  }
}
