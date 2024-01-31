define zulip_ops::ssh_authorized_keys(
  $keys = true,
) {
  $user = $name
  if $keys == true {
    $keypath = "prod/ssh/authorized_keys/${user}"
  } else {
    $keypath = "prod/ssh/authorized_keys/${keys}"
  }
  exec { "ssh_authorized_keys ${user}":
    require => File['/usr/local/bin/install-ssh-authorized-keys'],
    command => "/usr/local/bin/install-ssh-authorized-keys ${user} ${keypath}",
    unless  => "[ -f /usr/local/bin/install-ssh-authorized-keys ] && /usr/local/bin/install-ssh-authorized-keys ${user} ${keypath} check",
  }
}
