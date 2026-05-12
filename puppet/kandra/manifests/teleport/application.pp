# @summary Adds an http "application" to the Teleport configuration for the host.
#
# See https://goteleport.com/docs/application-access/
define kandra::teleport::application (
  $port,
  $description = '',
  $order = '50',
) {
  include kandra::teleport::application_top
  $app_data = [
    {
      name        => $name,
      description => $description,
      uri         => "http://127.0.0.1:${port}",
      labels      => {
        name => $name,
      },
    },
  ]

  # This is appended to puppet/kandra/files/teleport_node.yaml, so
  # must be indented, and the leading document dashes stripped.
  $app_yaml = to_yaml($app_data).regsubst(/\A---\s*\n/, '').regsubst(/^/, '    ', 'G')
  concat::fragment { "teleport_app_${name}":
    target  => '/etc/teleport_node.yaml',
    order   => $order,
    content => $app_yaml,
  }
}
