# @summary Adds a sysctl file, and immediately runs it.
define zulip::sysctl (
  $source = undef,
  $content = undef,
  $skip_docker = false,
) {
  file { "/etc/sysctl.d/40-${name}.conf":
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => $source,
    content => $content,
  }
  $onlyif = $skip_docker ? {
    true    => 'touch /proc/sys/net/core/somaxconn',
    default => undef,
  }
  exec { "sysctl_p_${name}":
    command     => "/sbin/sysctl -p /etc/sysctl.d/40-${name}.conf",
    subscribe   => File["/etc/sysctl.d/40-${name}.conf"],
    refreshonly => true,
    onlyif      => $onlyif,
  }
}
