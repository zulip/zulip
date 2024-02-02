# @summary Adds a sysctl file, and immediately runs it.
define zulip::sysctl (
  $key,
  $value,
  $order = 40,
  $comment = '',
) {
  if $comment == '' {
    $content = "${key} = ${value}\n"
  } else {
    $content = "# ${comment}\n${key} = ${value}\n"
  }
  file { "/etc/sysctl.d/${order}-${name}.conf":
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => $content,
  }

  # Try to touch the procfile before trying to adjust it -- if we're
  # in a containerized environment, failure to set this is not a fatal
  # exception.
  $procpath = regsubst($key, '\.', '/')
  exec { "sysctl_p_${name}":
    command     => "/sbin/sysctl -p /etc/sysctl.d/${order}-${name}.conf",
    subscribe   => File["/etc/sysctl.d/${order}-${name}.conf"],
    refreshonly => true,
    onlyif      => "touch /proc/sys/${procpath}",
  }
}
