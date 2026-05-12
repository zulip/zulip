define kandra::teleport::prometheus_app (
  $port,
  $description = '',
  $order = '50',
) {
  $app_name = regsubst("${facts['networking']['hostname']}-${name}", '_', '-', 'G')
  # Handle non-AWS hosts which don't have ec2 metadata
  $fallback_role = $facts['networking']['hostname'] ? {
    /^([^.-]+)/ => $1,
    default     => '',
  }
  $role = pick_default($facts.dig('ec2_metadata', 'tags', 'instance', 'role'), $fallback_role)
  kandra::teleport::application { $app_name:
    port        => $port,
    order       => $order,
    description => $description,
    labels      => {
      type     => 'prometheus',
      instance => $facts['networking']['hostname'],
      exporter => $name,
      role     => $role,
    }
  }
}
